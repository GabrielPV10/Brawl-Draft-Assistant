"""Cliente HTTP para la API oficial de Brawl Stars (developer.brawlstars.com).

Endpoints útiles para el proyecto:
    GET /players/%23{tag}                 -> brawlers, niveles, gadgets, star powers
    GET /players/%23{tag}/battlelog       -> últimas 25 partidas

Notas de despliegue:
- La API de Supercell exige una API key atada a IP fija. En Render (IPs dinámicas)
  se enruta vía proxy con IP fija (settings.supercell_proxy_url), cuya IP se
  registra en el token de Supercell.
- El caché en Redis es OPCIONAL: si no hay Redis disponible, se omite sin romper.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.schemas.team import BrawlerProficiency, PlayerProficiencyReport

logger = logging.getLogger("app.services.supercell")

# Modos competitivos 3v3 que cuentan para el winrate reciente del battlelog.
_COMPETITIVE_MODES = {
    "gemGrab", "brawlBall", "bounty", "heist", "hotZone", "knockout", "wipeout",
}


class SupercellClient:
    def __init__(self) -> None:
        s = get_settings()
        self.api_key = s.supercell_api_key
        self.base_url = s.supercell_api_base
        self.proxy = s.supercell_proxy_url or None
        self.cache_ttl = 3600  # 1h cache por jugador

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------ public

    async def fetch_player_proficiency(self, player_tag: str) -> PlayerProficiencyReport:
        """Pulla datos del jugador + battlelog y calcula proficiency por brawler.

        Retorna una lista vacía si no hay API key configurada o si hay error de red.
        """
        tag = self._normalize(player_tag)
        cached = self._cache_get(tag)
        if cached is not None:
            return PlayerProficiencyReport(**cached)

        if not self.api_key:
            return PlayerProficiencyReport(player_tag=tag, brawlers=[])

        try:
            player = await self._get(f"/players/%23{tag}")
            battlelog = await self._get(f"/players/%23{tag}/battlelog")
        except httpx.HTTPError:
            logger.exception("Fallo consultando Supercell para %s", tag)
            return PlayerProficiencyReport(player_tag=tag, brawlers=[])

        report = self._build_report(tag, player, battlelog)
        self._cache_set(tag, report.model_dump())
        return report

    # ---------------------------------------------------------------- private

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0))
    async def _get(self, path: str) -> dict[str, Any]:
        async with httpx.AsyncClient(
            base_url=self.base_url, timeout=10.0, proxy=self.proxy
        ) as client:
            resp = await client.get(path, headers=self._headers)
            resp.raise_for_status()
            return resp.json()

    def _build_report(
        self, tag: str, player: dict[str, Any], battlelog: dict[str, Any]
    ) -> PlayerProficiencyReport:
        """Construye el reporte aplicando la fórmula de proficiency por brawler."""
        nickname = player.get("name") if isinstance(player, dict) else None
        winrates = self._recent_winrates(tag, battlelog)

        brawlers: list[BrawlerProficiency] = []
        for b in player.get("brawlers", []) or []:
            bid = b.get("id")
            if bid is None:
                continue
            trophies = int(b.get("trophies", 0) or 0)
            highest = int(b.get("highestTrophies", trophies) or trophies)
            power = int(b.get("power", 0) or 0)
            gadgets = len(b.get("gadgets", []) or [])
            star_powers = len(b.get("starPowers", []) or [])
            recent = winrates.get(bid)

            score = proficiency_score(
                trophies=trophies,
                trophies_max=max(highest, 1),
                power_level=power,
                gadgets_unlocked=gadgets,
                star_powers_unlocked=star_powers,
                recent_winrate=recent,
            )
            brawlers.append(
                BrawlerProficiency(
                    brawler_id=bid,
                    brawler_name=str(b.get("name", "")).title(),
                    proficiency=score,
                    trophies=trophies,
                    power_level=power,
                    gadgets_unlocked=gadgets,
                    star_powers_unlocked=star_powers,
                    recent_winrate=recent,
                )
            )
        return PlayerProficiencyReport(player_tag=tag, nickname=nickname, brawlers=brawlers)

    def _recent_winrates(self, tag: str, battlelog: dict[str, Any]) -> dict[int, float]:
        """Winrate reciente por brawler_id, usando solo modos competitivos 3v3.

        Busca al jugador (por su tag) en cada partida para saber qué brawler usó
        y si ganó, y agrega victorias/total por brawler.
        """
        norm_self = self._bare_tag(tag)
        wins: dict[int, int] = {}
        total: dict[int, int] = {}

        for item in (battlelog.get("items", []) or []):
            battle = item.get("battle", {}) or {}
            if battle.get("mode") not in _COMPETITIVE_MODES:
                continue
            result = battle.get("result")  # "victory" | "defeat" | "draw"
            if result not in ("victory", "defeat"):
                continue
            bid = self._find_player_brawler(norm_self, battle)
            if bid is None:
                continue
            total[bid] = total.get(bid, 0) + 1
            if result == "victory":
                wins[bid] = wins.get(bid, 0) + 1

        return {bid: wins.get(bid, 0) / n for bid, n in total.items() if n > 0}

    def _find_player_brawler(self, norm_self: str, battle: dict[str, Any]) -> int | None:
        """Devuelve el id del brawler que usó el jugador en esa partida (o None)."""
        for team in (battle.get("teams", []) or []):
            for member in team:
                if self._bare_tag(member.get("tag", "")) == norm_self:
                    brawler = member.get("brawler", {}) or {}
                    return brawler.get("id")
        # Modos sin equipos (showdown) usan 'players'; no son competitivos 3v3, se ignoran.
        return None

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _normalize(tag: str) -> str:
        return urllib.parse.quote(tag.upper().lstrip("#"))

    @staticmethod
    def _bare_tag(tag: str) -> str:
        """Tag en mayúsculas sin '#' ni codificación, para comparar."""
        return urllib.parse.unquote(tag).upper().lstrip("#")

    def _cache_key(self, tag: str) -> str:
        return f"supercell:player:{tag}"

    def _cache_get(self, tag: str) -> dict[str, Any] | None:
        """Lee del caché. Si Redis no está disponible, devuelve None sin romper."""
        try:
            from app.db.redis_client import get_redis

            raw = get_redis().get(self._cache_key(tag))
            return json.loads(raw) if raw else None
        except Exception:  # noqa: BLE001 - el caché es opcional
            return None

    def _cache_set(self, tag: str, payload: dict[str, Any]) -> None:
        """Guarda en caché. Si Redis no está disponible, no hace nada."""
        try:
            from app.db.redis_client import get_redis

            get_redis().setex(self._cache_key(tag), self.cache_ttl, json.dumps(payload, default=str))
        except Exception:  # noqa: BLE001 - el caché es opcional
            pass


def proficiency_score(
    *,
    trophies: int,
    trophies_max: int,
    power_level: int,
    gadgets_unlocked: int,
    star_powers_unlocked: int,
    recent_winrate: float | None,
) -> float:
    """Aplica la fórmula del plan (escala 0-100).

    0.30 · normalizar(trofeos)
  + 0.20 · (nivel_poder / 11)
  + 0.15 · gadgets
  + 0.15 · star_powers
  + 0.20 · winrate_reciente
    """
    norm_trophies = min(trophies / max(trophies_max, 1), 1.0)
    norm_power = min(power_level / 11.0, 1.0)
    norm_gadgets = min(gadgets_unlocked / 2.0, 1.0)
    norm_starpwr = min(star_powers_unlocked / 2.0, 1.0)
    norm_winrate = recent_winrate if recent_winrate is not None else 0.5

    score = (
        0.30 * norm_trophies
        + 0.20 * norm_power
        + 0.15 * norm_gadgets
        + 0.15 * norm_starpwr
        + 0.20 * norm_winrate
    )
    return round(score * 100.0, 2)
