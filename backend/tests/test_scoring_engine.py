"""Tests del ScoringEngine usando SQLite en memoria sembrado con datos sintéticos."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.brawler import Brawler
from app.models.map import Map
from app.models.map_stats import MapStats
from app.models.player_proficiency import PlayerProficiency
from app.models.synergy import Synergy
from app.models.team_profile import TeamProfile, TeamProfileMember
from app.schemas.draft import DraftPhase, DraftRequest
from app.services.scoring import PHASE_WEIGHT_MULTIPLIERS, ScoringEngine


# ---------------------------------------------------------------- fixtures


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, future=True)
    db = Session()
    try:
        _seed(db)
        yield db
    finally:
        db.close()


MAP_ID = 15040002

# Brawler IDs sintéticos
PIPER = 16000000
BONNIE = 16000037
MANDY = 16000054
COLT = 16000001
BULL = 16000002


def _seed(db) -> None:
    """Datos sintéticos diseñados para hacer ranking predecible:

    En el mapa MAP_ID:
      - Piper: winrate 0.60, pickrate 0.30  (mejor en abstracto)
      - Bonnie: winrate 0.58, pickrate 0.40
      - Mandy: winrate 0.55, pickrate 0.20
      - Colt: winrate 0.45, pickrate 0.10
      - Bull: winrate 0.40, pickrate 0.05  (peor)

    Counter: Mandy counterea fuerte a Bonnie (score 0.5)
    Sinergia: Piper + Colt funcionan juntos (score 0.4 en este mapa)
    """
    for bid, name in [
        (PIPER, "Piper"),
        (BONNIE, "Bonnie"),
        (MANDY, "Mandy"),
        (COLT, "Colt"),
        (BULL, "Bull"),
    ]:
        db.add(Brawler(id=bid, name=name, slug=name.lower()))
    db.add(Map(id=MAP_ID, name="Out in the Open", slug="out-in-the-open", game_mode="Knockout"))
    db.flush()

    stats = [
        (PIPER, 0.60, 0.30),
        (BONNIE, 0.58, 0.40),
        (MANDY, 0.55, 0.20),
        (COLT, 0.45, 0.10),
        (BULL, 0.40, 0.05),
    ]
    for bid, wr, pr in stats:
        db.add(MapStats(map_id=MAP_ID, brawler_id=bid, winrate=wr, pickrate=pr))

    db.add(
        Synergy(b1_id=MANDY, b2_id=BONNIE, relation_type="counter", score=0.5, map_id=None)
    )
    db.add(
        Synergy(b1_id=PIPER, b2_id=COLT, relation_type="synergy", score=0.4, map_id=MAP_ID)
    )
    db.add(
        Synergy(b1_id=COLT, b2_id=PIPER, relation_type="synergy", score=0.4, map_id=MAP_ID)
    )
    db.commit()


# ------------------------------------------------------------ tests de pesos


def test_adjust_weights_first_pick_raises_winrate_and_counterable(db_session):
    engine = ScoringEngine(db_session)
    base = engine.weights
    adjusted = engine._adjust_weights(DraftPhase.FIRST_PICK)
    assert adjusted.w1_winrate_mapa == pytest.approx(
        base.w1_winrate_mapa * PHASE_WEIGHT_MULTIPLIERS[DraftPhase.FIRST_PICK]["w1_winrate_mapa"]
    )
    assert adjusted.w6_counterable == pytest.approx(
        base.w6_counterable * PHASE_WEIGHT_MULTIPLIERS[DraftPhase.FIRST_PICK]["w6_counterable"]
    )
    # w2 baja
    assert adjusted.w2_counter_score < base.w2_counter_score


def test_adjust_weights_mid_picks_unchanged(db_session):
    engine = ScoringEngine(db_session)
    base = engine.weights
    adjusted = engine._adjust_weights(DraftPhase.MID_PICKS)
    assert adjusted == base


def test_adjust_weights_last_pick_emphasizes_counter(db_session):
    engine = ScoringEngine(db_session)
    base = engine.weights
    adjusted = engine._adjust_weights(DraftPhase.LAST_PICK)
    assert adjusted.w2_counter_score > base.w2_counter_score
    assert adjusted.w6_counterable < base.w6_counterable


# -------------------------------------------------- tests de enumeración


def test_enumerate_candidates_excludes_bans_allies_enemies(db_session):
    engine = ScoringEngine(db_session)
    req = DraftRequest(
        map_id=MAP_ID,
        phase=DraftPhase.MID_PICKS,
        allies=[PIPER],
        enemies=[BONNIE],
        bans=[MANDY],
    )
    ids = {bid for bid, _ in engine._enumerate_candidates(req, None)}
    assert PIPER not in ids
    assert BONNIE not in ids
    assert MANDY not in ids
    assert COLT in ids
    assert BULL in ids


def test_enumerate_candidates_with_player_tag_filters_by_roster(db_session):
    db_session.add(
        PlayerProficiency(
            player_tag="ABC", brawler_id=PIPER, proficiency=80.0, power_level=11, trophies=500
        )
    )
    db_session.add(
        PlayerProficiency(
            player_tag="ABC", brawler_id=COLT, proficiency=60.0, power_level=9, trophies=300
        )
    )
    db_session.commit()
    engine = ScoringEngine(db_session)
    req = DraftRequest(map_id=MAP_ID, phase=DraftPhase.MID_PICKS)
    ids = {bid for bid, _ in engine._enumerate_candidates(req, "ABC")}
    # Sólo los dos que tiene desbloqueados deben aparecer
    assert ids == {PIPER, COLT}


# -------------------------------------------------- tests de sub-factores


def test_winrate_y_pickrate_devuelven_valores_sembrados(db_session):
    engine = ScoringEngine(db_session)
    assert engine._winrate_mapa(PIPER, MAP_ID) == pytest.approx(0.60)
    assert engine._pickrate_relativo(PIPER, MAP_ID) == pytest.approx(0.30)
    # brawler sin stats devuelve 0
    assert engine._winrate_mapa(99999, MAP_ID) == 0.0


def test_counter_score_promedia_enemigos(db_session):
    engine = ScoringEngine(db_session)
    # Mandy counterea a Bonnie con 0.5
    assert engine._counter_score(MANDY, [BONNIE]) == pytest.approx(0.5)
    # Sin enemigos => 0
    assert engine._counter_score(MANDY, []) == 0.0


def test_sinergia_mapa_especifica(db_session):
    engine = ScoringEngine(db_session)
    assert engine._sinergia(PIPER, [COLT], MAP_ID) == pytest.approx(0.4)
    assert engine._sinergia(PIPER, [], MAP_ID) == 0.0


def test_ban_risk_solo_aplica_en_first_pick(db_session):
    engine = ScoringEngine(db_session)
    # Piper: avg(0.30) * avg(0.60) = 0.18
    assert engine._ban_risk(PIPER, DraftPhase.FIRST_PICK) == pytest.approx(0.18)
    # En otras fases es 0
    assert engine._ban_risk(PIPER, DraftPhase.MID_PICKS) == 0.0
    assert engine._ban_risk(PIPER, DraftPhase.LAST_PICK) == 0.0


# -------------------------------------------------- test integral de ranking


def test_score_candidates_ranks_piper_first_on_neutral_map(db_session):
    """En mid_picks sin allies/enemies, el mejor winrate gana."""
    engine = ScoringEngine(db_session)
    req = DraftRequest(map_id=MAP_ID, phase=DraftPhase.MID_PICKS)
    recs = engine.score_candidates(req)
    assert len(recs) == 5
    # Piper tiene el mejor winrate (0.60)
    assert recs[0].brawler_name == "Piper"
    # Bull tiene el peor (0.40)
    assert recs[-1].brawler_name == "Bull"


def test_score_candidates_last_pick_prioritizes_counter(db_session):
    """En last_pick contra Bonnie, Mandy debe subir por encima de Piper."""
    engine = ScoringEngine(db_session)
    req = DraftRequest(map_id=MAP_ID, phase=DraftPhase.LAST_PICK, enemies=[BONNIE])
    recs = engine.score_candidates(req)
    rec_names = [r.brawler_name for r in recs]
    # Mandy debe estar entre los primeros porque counterea a Bonnie
    assert rec_names[0] == "Mandy"


def test_score_candidates_personal_proficiency_lifts_known_brawler(db_session):
    """Si el jugador domina a Colt al 100%, Colt debe subir el ranking."""
    profile = TeamProfile(owner_id="device-1", name="Squad")
    profile.members = [TeamProfileMember(slot=0, player_tag="MAUR", nickname="Mauricio")]
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)

    # Mauricio domina Colt al 100, no tiene los otros
    db_session.add(
        PlayerProficiency(
            player_tag="MAUR",
            brawler_id=COLT,
            proficiency=100.0,
            power_level=11,
            trophies=1000,
            gadgets_unlocked=2,
            star_powers_unlocked=2,
        )
    )
    db_session.add(
        PlayerProficiency(
            player_tag="MAUR", brawler_id=BULL, proficiency=10.0, power_level=3, trophies=50
        )
    )
    db_session.commit()

    engine = ScoringEngine(db_session)
    req = DraftRequest(
        map_id=MAP_ID,
        phase=DraftPhase.MID_PICKS,
        profile_id=profile.id,
        slot=0,
    )
    recs = engine.score_candidates(req)
    # Sólo aparecen brawlers del roster del jugador
    names = [r.brawler_name for r in recs]
    assert set(names) == {"Colt", "Bull"}
    # Colt arriba por proficiency alta
    assert recs[0].brawler_name == "Colt"
