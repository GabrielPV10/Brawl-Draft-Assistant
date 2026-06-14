"""Cliente HTTP para la API oficial de Brawl Stars (developer.brawlstars.com).

Endpoints útiles para el proyecto:
    GET /players/%23{tag}                 -> brawlers, niveles, gadgets, star powers
    GET /players/%23{tag}/battlelog       -> últimas 25 partidas

Se cachea en Redis con TTL 1h por player_tag (ver settings.cache_ttl_seconds).
"""

from __future__ import annotations

import json
import urllib.parse
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.db.redis_client import get_redis
from app.schemas.team import BrawlerProficiency, PlayerProficiencyReport


class SupercellClient:
    def __init__(self) -> None:
        s = get_settings()
        self.api_key = s.supercell_api_key
        self.base_url = s.supercell_api_base
        self.cache_ttl = 3600  # 1h cache por jugador (no usa el TTL global de Brawlify)

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------ public

    async def fetch_player_proficiency(self, player_tag: str) -> PlayerProficiencyReport:
        """Pulla datos del jugador + battlelog y calcula proficiency por brawler.

        Stub: retorna una lista vacía si no hay API key configurada o si hay error.
        """
        tag = self._normalize(player_tag)
        cached = self._cache_get(tag)
        if cached is not None:
            return PlayerProficiencyReport(**cached)

        if not self.api_key:
            return PlayerProficiencyReport(player_tag=tag, brawlers=[])

        player = await self._get(f"/players/%23{tag}")
        battlelog = await self._get(f"/players/%23{tag}/battlelog")

        report = self._build_report(tag, player, battlelog)
        self._cache_set(tag, report.model_dump())
        return report

    # ---------------------------------------------------------------- private

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0))
    async def _get(self, path: str) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            resp = await client.get(path, headers=self._headers)
            resp.raise_for_status()
            return resp.json()

    def _build_report(
        self, tag: str, player: dict[str, Any], battlelog: dict[str, Any]
    ) -> PlayerProficiencyReport:
        """Construye el reporte aplicando la fórmula de proficiency.

        Stub: implementación real pendiente. Por ahora pasa un esqueleto vacío.
        """
        # TODO: derivar BrawlerProficiency por cada brawler en player['brawlers'].
        # winrate_reciente sale de battlelog['items'] filtrando por modo competitivo.
        _ = battlelog
        nickname = player.get("name") if isinstance(player, dict) else None
        return PlayerProficiencyReport(player_tag=tag, nickname=nickname, brawlers=[])

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _normalize(tag: str) -> str:
        return urllib.parse.quote(tag.upper().lstrip("#"))

    def _cache_key(self, tag: str) -> str:
        return f"supercell:player:{tag}"

    def _cache_get(self, tag: str) -> dict[str, Any] | None:
        raw = get_redis().get(self._cache_key(tag))
        return json.loads(raw) if raw else None

    def _cache_set(self, tag: str, payload: dict[str, Any]) -> None:
        get_redis().setex(self._cache_key(tag), self.cache_ttl, json.dumps(payload, default=str))


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
