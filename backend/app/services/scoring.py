"""Motor de scoring del draft.

Fórmula (ver docs/algoritmo-draft.md):
    Score(b, mapa, aliados, enemigos, fase, jugador) =
        w1 · winrate_mapa(b)
      + w2 · counter_score(b, enemigos)
      + w3 · sinergia(b, aliados)
      + w4 · pickrate_relativo(b)
      - w5 · ban_risk(b, fase)
      - w6 · counterable_score(b)
      + w7 · personal_proficiency(b, jugador)

Los pesos vienen de la config; se ajustan dinámicamente por fase del draft.
Los sub-cálculos viven en métodos separados para poder testearlos aisladamente.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.config import ScoringWeights, get_settings
from app.models.brawler import Brawler
from app.models.map_stats import MapStats
from app.models.player_proficiency import PlayerProficiency
from app.models.synergy import Synergy
from app.models.team_profile import TeamProfile, TeamProfileMember
from app.schemas.draft import DraftPhase, DraftRecommendation, DraftRequest


@dataclass
class FactorBreakdown:
    winrate_mapa: float = 0.0
    counter_score: float = 0.0
    sinergia: float = 0.0
    pickrate_relativo: float = 0.0
    ban_risk: float = 0.0
    counterable: float = 0.0
    personal_proficiency: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "winrate_mapa": self.winrate_mapa,
            "counter_score": self.counter_score,
            "sinergia": self.sinergia,
            "pickrate_relativo": self.pickrate_relativo,
            "ban_risk": self.ban_risk,
            "counterable": self.counterable,
            "personal_proficiency": self.personal_proficiency,
        }


# Presets de estrategia: el usuario decide qué factores importan. Cada preset
# REEMPLAZA los pesos base (los que no aparecen quedan en su default).
# "balanced" = vacío = usa los pesos por defecto de la config.
# Cada preset deja un peso pequeño de winrate como desempate, para que el ranking
# tenga sentido aun cuando el factor principal esté empatado o sea escaso (p.ej.
# sinergia con pocos datos). El factor elegido domina; winrate solo desempata.
STRATEGY_WEIGHTS: dict[str, dict[str, float]] = {
    "balanced": {},
    "counter": {
        "w1_winrate_mapa": 0.3,   # desempate
        "w2_counter_score": 1.6,  # domina
        "w3_sinergia": 0.0,
        "w4_pickrate_relativo": 0.0,
        "w5_ban_risk": 0.0,
        "w6_counterable": 0.3,
        "w7_personal_proficiency": 0.0,
    },
    "winrate": {
        "w1_winrate_mapa": 1.6,   # domina
        "w2_counter_score": 0.0,
        "w3_sinergia": 0.0,
        "w4_pickrate_relativo": 0.3,
        "w5_ban_risk": 0.0,
        "w6_counterable": 0.0,
        "w7_personal_proficiency": 0.0,
    },
    "synergy": {
        "w1_winrate_mapa": 0.4,   # desempate
        "w2_counter_score": 0.0,
        "w3_sinergia": 1.6,       # domina
        "w4_pickrate_relativo": 0.0,
        "w5_ban_risk": 0.0,
        "w6_counterable": 0.0,
        "w7_personal_proficiency": 0.0,
    },
}


# Multiplicadores aplicados a los pesos base por fase del draft.
# Ver tabla en docs/algoritmo-draft.md.
PHASE_WEIGHT_MULTIPLIERS: dict[DraftPhase, dict[str, float]] = {
    DraftPhase.FIRST_PICK: {
        "w1_winrate_mapa": 1.30,
        "w2_counter_score": 0.40,
        "w6_counterable": 1.50,
    },
    DraftPhase.MID_PICKS: {},  # pesos estándar
    DraftPhase.LAST_PICK: {
        "w2_counter_score": 1.50,
        "w3_sinergia": 1.30,
        "w6_counterable": 0.20,
    },
}


class ScoringEngine:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.weights = get_settings().weights

    # ------------------------------------------------------------------ public

    def score_candidates(self, req: DraftRequest) -> list[DraftRecommendation]:
        """Calcula y rankea todos los brawlers candidatos."""
        adjusted = self._resolve_weights(req)

        # Precarga de datos comunes para evitar N+1 queries
        target_tag = self._target_player_tag(req)
        proficiency_lookup = self._load_proficiency_lookup(target_tag) if target_tag else {}

        recs: list[DraftRecommendation] = []
        for brawler_id, brawler_name in self._enumerate_candidates(req, target_tag):
            factors = self._compute_factors(
                brawler_id, req, proficiency_lookup.get(brawler_id, 0.0)
            )
            score = self._apply_weights(factors, adjusted)
            recs.append(
                DraftRecommendation(
                    brawler_id=brawler_id,
                    brawler_name=brawler_name,
                    score=round(score, 4),
                    breakdown=factors.as_dict(),
                )
            )
        recs.sort(key=lambda r: r.score, reverse=True)
        return recs

    # ---------------------------------------------------------------- private

    def _resolve_weights(self, req: DraftRequest) -> ScoringWeights:
        """Pesos finales = preset de estrategia, luego multiplicadores de fase.

        Primero la estrategia elegida por el usuario reemplaza los pesos base
        (counter/winrate/synergy/balanced); después se aplican los ajustes por
        fase del draft sobre ese resultado.
        """
        base = self.weights
        preset = STRATEGY_WEIGHTS.get(req.strategy, {})
        if preset:
            base = base.model_copy(update=preset)
        return self._adjust_weights(base, req.phase)

    def _adjust_weights(self, base: ScoringWeights, phase: DraftPhase) -> ScoringWeights:
        """Aplica los multiplicadores de fase sobre `base`."""
        multipliers = PHASE_WEIGHT_MULTIPLIERS.get(phase, {})
        if not multipliers:
            return base
        kwargs = {attr: getattr(base, attr) * mult for attr, mult in multipliers.items()}
        return base.model_copy(update=kwargs)

    def _enumerate_candidates(
        self, req: DraftRequest, target_tag: str | None
    ) -> list[tuple[int, str]]:
        """Lista de (brawler_id, name) candidatos.

        Excluye baneados, aliados y enemigos. Si hay target_tag, además filtra
        por el roster del jugador (sólo brawlers que tenga desbloqueados).
        """
        excluded = set(req.bans) | set(req.allies) | set(req.enemies)
        stmt = select(Brawler.id, Brawler.name)
        if excluded:
            stmt = stmt.where(~Brawler.id.in_(excluded))

        if target_tag is not None:
            # Inner join: si el brawler no aparece en player_proficiency, queda fuera
            stmt = stmt.join(
                PlayerProficiency, PlayerProficiency.brawler_id == Brawler.id
            ).where(PlayerProficiency.player_tag == target_tag)

        return list(self.db.execute(stmt).all())

    def _compute_factors(
        self, brawler_id: int, req: DraftRequest, personal_proficiency: float
    ) -> FactorBreakdown:
        return FactorBreakdown(
            winrate_mapa=self._winrate_mapa(brawler_id, req.map_id),
            counter_score=self._counter_score(brawler_id, req.enemies),
            sinergia=self._sinergia(brawler_id, req.allies, req.map_id),
            pickrate_relativo=self._pickrate_relativo(brawler_id, req.map_id),
            ban_risk=self._ban_risk(brawler_id, req.phase),
            counterable=self._counterable(brawler_id),
            personal_proficiency=personal_proficiency,
        )

    def _apply_weights(self, f: FactorBreakdown, w: ScoringWeights) -> float:
        return (
            w.w1_winrate_mapa * f.winrate_mapa
            + w.w2_counter_score * f.counter_score
            + w.w3_sinergia * f.sinergia
            + w.w4_pickrate_relativo * f.pickrate_relativo
            - w.w5_ban_risk * f.ban_risk
            - w.w6_counterable * f.counterable
            + w.w7_personal_proficiency * f.personal_proficiency
        )

    # ----------------------------------------------- sub-cálculos (con queries)

    def _winrate_mapa(self, brawler_id: int, map_id: int) -> float:
        """Winrate del brawler en ese mapa. 0.0 si no hay dato."""
        stmt = select(MapStats.winrate).where(
            MapStats.brawler_id == brawler_id, MapStats.map_id == map_id
        )
        result = self.db.execute(stmt).scalar()
        return float(result) if result is not None else 0.0

    def _pickrate_relativo(self, brawler_id: int, map_id: int) -> float:
        """Pickrate del brawler en ese mapa. 0.0 si no hay dato."""
        stmt = select(MapStats.pickrate).where(
            MapStats.brawler_id == brawler_id, MapStats.map_id == map_id
        )
        result = self.db.execute(stmt).scalar()
        return float(result) if result is not None else 0.0

    def _counter_score(self, brawler_id: int, enemies: list[int]) -> float:
        """Promedio de qué tan bien `brawler_id` le gana a cada enemigo pickeado.

        Lee `synergies` con relation_type='counter' donde b1=brawler_id, b2=enemy.
        Score positivo = me beneficia, negativo = me perjudica.
        """
        if not enemies:
            return 0.0
        stmt = select(func.avg(Synergy.score)).where(
            Synergy.b1_id == brawler_id,
            Synergy.b2_id.in_(enemies),
            Synergy.relation_type == "counter",
        )
        result = self.db.execute(stmt).scalar()
        return float(result) if result is not None else 0.0

    def _sinergia(self, brawler_id: int, allies: list[int], map_id: int) -> float:
        """Promedio de sinergia con aliados, preferentemente para este mapa.

        Si hay relación específica del mapa la usa; si no, cae al global.
        """
        if not allies:
            return 0.0
        # Buscar sinergia mapa-específica
        stmt = select(func.avg(Synergy.score)).where(
            and_(
                Synergy.b1_id == brawler_id,
                Synergy.b2_id.in_(allies),
                Synergy.relation_type == "synergy",
                Synergy.map_id == map_id,
            )
        )
        result = self.db.execute(stmt).scalar()
        if result is not None:
            return float(result)
        # Fallback: global
        stmt = select(func.avg(Synergy.score)).where(
            Synergy.b1_id == brawler_id,
            Synergy.b2_id.in_(allies),
            Synergy.relation_type == "synergy",
            Synergy.map_id.is_(None),
        )
        result = self.db.execute(stmt).scalar()
        return float(result) if result is not None else 0.0

    def _ban_risk(self, brawler_id: int, phase: DraftPhase) -> float:
        """Riesgo de que el enemigo banee. Sólo importa en first_pick.

        Aproximación: pickrate promedio global * winrate promedio global.
        Brawlers OP y muy pickeados son más probables de ser baneados.
        """
        if phase != DraftPhase.FIRST_PICK:
            return 0.0
        stmt = select(
            func.avg(MapStats.pickrate),
            func.avg(MapStats.winrate),
        ).where(MapStats.brawler_id == brawler_id)
        avg_pick, avg_win = self.db.execute(stmt).one_or_none() or (None, None)
        if avg_pick is None or avg_win is None:
            return 0.0
        return float(avg_pick) * float(avg_win)

    def _counterable(self, brawler_id: int) -> float:
        """Qué tan facilmente countereable es. Promedio de cuántos brawlers le ganan."""
        # Brawlers que GANAN a brawler_id => Synergy(b1=otro, b2=brawler_id, counter, score>0)
        stmt = select(func.avg(Synergy.score)).where(
            Synergy.b2_id == brawler_id,
            Synergy.relation_type == "counter",
            Synergy.score > 0,
        )
        result = self.db.execute(stmt).scalar()
        return float(result) if result is not None else 0.0

    # ------------------------------------------------- personal proficiency

    def _target_player_tag(self, req: DraftRequest) -> str | None:
        """Resuelve el player_tag del slot indicado en el perfil."""
        if req.profile_id is None or req.slot is None:
            return None
        stmt = select(TeamProfileMember.player_tag).where(
            TeamProfileMember.profile_id == req.profile_id,
            TeamProfileMember.slot == req.slot,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def _load_proficiency_lookup(self, player_tag: str) -> dict[int, float]:
        """Trae el dominio (0-100) de cada brawler para ese player_tag.

        Lo escalamos a 0.0-1.0 para que sea comparable con winrate/pickrate
        antes de multiplicarlo por su peso w7.
        """
        stmt = select(PlayerProficiency.brawler_id, PlayerProficiency.proficiency).where(
            PlayerProficiency.player_tag == player_tag
        )
        return {row.brawler_id: row.proficiency / 100.0 for row in self.db.execute(stmt)}

    # ------------------------------------------------- evaluación de equipos completos

    def evaluate_team(
        self,
        map_id: int,
        allies: list[int],
        enemies: list[int],
    ) -> dict:
        """Estima la probabilidad de victoria comparando ambos equipos pick a pick.

        Para cada brawler calcula su valor con pesos balanced (sin fase), usando
        al otro equipo como enemigos y a sus compañeros como aliados.
        La probabilidad usa una función sigmoide: 50% base, ±50% por diferencia.
        """
        w = self.weights

        def _score_brawler(brawler_id: int, allies_ctx: list[int], enemies_ctx: list[int]) -> float:
            factors = FactorBreakdown(
                winrate_mapa=self._winrate_mapa(brawler_id, map_id),
                counter_score=self._counter_score(brawler_id, enemies_ctx),
                sinergia=self._sinergia(brawler_id, allies_ctx, map_id),
                pickrate_relativo=self._pickrate_relativo(brawler_id, map_id),
                ban_risk=0.0,
                counterable=self._counterable(brawler_id),
                personal_proficiency=0.0,
            )
            return self._apply_weights(factors, w)

        our_scores = [
            _score_brawler(a, [x for x in allies if x != a], enemies)
            for a in allies
        ]
        enemy_scores = [
            _score_brawler(e, [x for x in enemies if x != e], allies)
            for e in enemies
        ]

        our_avg = sum(our_scores) / max(len(our_scores), 1)
        enemy_avg = sum(enemy_scores) / max(len(enemy_scores), 1)

        # sigmoid: diff=0 → 50%, diff=+0.5 → ~73%, diff=+1.0 → ~88%
        diff = our_avg - enemy_avg
        win_prob = 50.0 + 50.0 * math.tanh(diff * 2.5)

        return {
            "win_probability": round(win_prob, 1),
            "our_avg_score": round(our_avg, 4),
            "enemy_avg_score": round(enemy_avg, 4),
        }

    # ------------------------------------------------- helper público de test

    def _resolve_target_player_tag(self, req: DraftRequest) -> str | None:
        """Wrapper público sobre _target_player_tag (sólo para tests)."""
        return self._target_player_tag(req)


def resolve_owner_profile(db: Session, owner_id: str, profile_id: int) -> TeamProfile | None:
    """Helper: valida que el perfil exista y pertenezca al owner."""
    stmt = select(TeamProfile).where(
        TeamProfile.id == profile_id, TeamProfile.owner_id == owner_id
    )
    return db.execute(stmt).scalar_one_or_none()
