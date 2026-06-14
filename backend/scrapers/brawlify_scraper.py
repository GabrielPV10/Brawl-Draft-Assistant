"""Scraper de brawlify.com/maps/{slug}.

Estrategia:
  1) Buscar un blob de datos embebido en la página (Next.js suele inyectar
     __NEXT_DATA__ con la info). Si está, parseamos JSON.
  2) Fallback: HTML scraping de tablas con BeautifulSoup. Selectores marcados
     como TODO porque hay que calibrarlos contra el HTML real en la primera
     corrida.

Rate-limited a 1 req/seg y respetando robots.txt. Cachea respuestas crudas en
Redis con TTL de 6h (ver settings.cache_ttl_seconds).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.db.redis_client import get_redis
from scrapers.sources.base import BrawlerMapStat, MapScrapeResult, TeamComp

logger = logging.getLogger(__name__)


class BrawlifyStatsSource:
    """Fuente real basada en Brawlify. Implementa MapStatsSource (LSP).

    Nota operacional: brawlify.com está tras Cloudflare y la API pública de
    BrawlAPI no expone winrates, así que esta fuente hoy puede no traer datos.
    Se conserva como contrato cumplido; la fuente real efectiva es MockStatsSource
    hasta resolver el acceso a datos (ver docs de Fase 2).
    """

    def __init__(self) -> None:
        s = get_settings()
        self.base_url = s.brawlify_base_url
        self.user_agent = s.brawlify_user_agent
        self.rate_limit = s.brawlify_rate_limit_seconds
        self.cache_ttl = s.cache_ttl_seconds
        self._last_request_at: float = 0.0

    async def fetch_map(self, map_slug: str) -> MapScrapeResult:
        cached = self._cache_get(map_slug)
        if cached is not None:
            return self._deserialize(cached)

        html = await self._get(f"/maps/{map_slug}")
        result = self._parse(map_slug, html)
        self._cache_set(map_slug, result)
        return result

    # ---------------------------------------------------------------- HTTP

    async def _get(self, path: str) -> str:
        await self._respect_rate_limit()
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=15.0,
            headers={"User-Agent": self.user_agent},
            follow_redirects=True,
        ) as client:
            resp = await client.get(path)
            resp.raise_for_status()
            return resp.text

    async def _respect_rate_limit(self) -> None:
        now = asyncio.get_event_loop().time()
        wait = self.rate_limit - (now - self._last_request_at)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_request_at = asyncio.get_event_loop().time()

    # -------------------------------------------------------------- parsing

    def _parse(self, map_slug: str, html: str) -> MapScrapeResult:
        soup = BeautifulSoup(html, "lxml")

        next_data = self._extract_next_data(soup)
        if next_data is not None:
            try:
                return self._parse_from_next_data(map_slug, next_data)
            except Exception:
                logger.exception("Fallo parseando __NEXT_DATA__ de %s", map_slug)

        # Fallback: HTML directo
        stats = self._parse_brawler_stats_html(soup)
        team_comps = self._parse_team_comps_html(soup)
        return MapScrapeResult(map_slug=map_slug, stats=stats, team_comps=team_comps)

    def _extract_next_data(self, soup: BeautifulSoup) -> dict[str, Any] | None:
        tag = soup.find("script", id="__NEXT_DATA__")
        if not tag or not tag.string:
            return None
        try:
            return json.loads(tag.string)
        except json.JSONDecodeError:
            return None

    def _parse_from_next_data(
        self, map_slug: str, data: dict[str, Any]
    ) -> MapScrapeResult:
        """Extrae stats del JSON embebido por Next.js.

        La forma exacta del JSON cambia entre versiones de Brawlify. Hacemos
        navegación tolerante: si no encontramos los nodos esperados retornamos
        listas vacías y dejamos que el caller registre el problema.
        """
        page_props = (
            data.get("props", {}).get("pageProps", {}) if isinstance(data, dict) else {}
        )
        stats_raw = page_props.get("stats") or page_props.get("brawlerStats") or []
        comps_raw = page_props.get("teamComps") or page_props.get("compositions") or []

        stats: list[BrawlerMapStat] = []
        for s in stats_raw:
            slug = s.get("brawler") or s.get("slug") or s.get("name", "").lower()
            if not slug:
                continue
            stats.append(
                BrawlerMapStat(
                    brawler_slug=str(slug).lower(),
                    winrate=_as_fraction(s.get("winRate") or s.get("winrate")),
                    pickrate=_as_fraction(s.get("pickRate") or s.get("pickrate")),
                    use_rate=_as_fraction_or_none(s.get("useRate") or s.get("userate")),
                    sample_size=_as_int_or_none(s.get("samples") or s.get("sampleSize")),
                )
            )

        team_comps: list[TeamComp] = []
        for c in comps_raw:
            brawlers = c.get("brawlers") or c.get("comp") or []
            if isinstance(brawlers, list) and len(brawlers) >= 3:
                slugs = tuple(str(b).lower() for b in brawlers[:3])  # type: ignore[assignment]
                team_comps.append(
                    TeamComp(
                        brawler_slugs=slugs,  # type: ignore[arg-type]
                        winrate=_as_fraction(c.get("winRate") or c.get("winrate")),
                        sample_size=_as_int_or_none(
                            c.get("samples") or c.get("sampleSize")
                        ),
                    )
                )

        return MapScrapeResult(map_slug=map_slug, stats=stats, team_comps=team_comps)

    def _parse_brawler_stats_html(self, soup: BeautifulSoup) -> list[BrawlerMapStat]:
        """Fallback: parsear tabla HTML. Selectores tentativos.

        TODO calibrar contra el HTML real en la primera corrida del scraper.
        """
        rows = soup.select("table.brawler-stats tbody tr") or soup.select(
            "[data-testid='brawler-stats-row']"
        )
        out: list[BrawlerMapStat] = []
        for row in rows:
            slug_el = row.select_one("[data-brawler-slug]") or row.select_one(".brawler-name")
            wr_el = row.select_one(".winrate") or row.select_one("[data-winrate]")
            pr_el = row.select_one(".pickrate") or row.select_one("[data-pickrate]")
            if not (slug_el and wr_el and pr_el):
                continue
            out.append(
                BrawlerMapStat(
                    brawler_slug=(
                        slug_el.get("data-brawler-slug") or slug_el.text.strip().lower()
                    ),
                    winrate=_parse_percent(wr_el.text),
                    pickrate=_parse_percent(pr_el.text),
                )
            )
        return out

    def _parse_team_comps_html(self, soup: BeautifulSoup) -> list[TeamComp]:
        """Fallback: parsear team comps de HTML. TODO calibrar."""
        cards = soup.select("[data-testid='team-comp-card']") or soup.select(".team-comp")
        out: list[TeamComp] = []
        for card in cards:
            slugs_el = card.select("[data-brawler-slug]")
            wr_el = card.select_one(".winrate") or card.select_one("[data-winrate]")
            if len(slugs_el) < 3 or not wr_el:
                continue
            slugs = tuple(
                (e.get("data-brawler-slug") or e.text.strip().lower()) for e in slugs_el[:3]
            )
            out.append(
                TeamComp(brawler_slugs=slugs, winrate=_parse_percent(wr_el.text))  # type: ignore[arg-type]
            )
        return out

    # ----------------------------------------------------------------- cache

    def _cache_key(self, slug: str) -> str:
        return f"brawlify:map:{slug}"

    def _cache_get(self, slug: str) -> dict[str, Any] | None:
        raw = get_redis().get(self._cache_key(slug))
        return json.loads(raw) if raw else None

    def _cache_set(self, slug: str, result: MapScrapeResult) -> None:
        get_redis().setex(
            self._cache_key(slug),
            self.cache_ttl,
            json.dumps(self._serialize(result), default=str),
        )

    @staticmethod
    def _serialize(r: MapScrapeResult) -> dict[str, Any]:
        return {
            "map_slug": r.map_slug,
            "scraped_at": r.scraped_at.isoformat(),
            "stats": [
                {
                    "brawler_slug": s.brawler_slug,
                    "winrate": s.winrate,
                    "pickrate": s.pickrate,
                    "use_rate": s.use_rate,
                    "sample_size": s.sample_size,
                }
                for s in r.stats
            ],
            "team_comps": [
                {
                    "brawler_slugs": list(c.brawler_slugs),
                    "winrate": c.winrate,
                    "sample_size": c.sample_size,
                }
                for c in r.team_comps
            ],
        }

    @staticmethod
    def _deserialize(payload: dict[str, Any]) -> MapScrapeResult:
        return MapScrapeResult(
            map_slug=payload["map_slug"],
            stats=[
                BrawlerMapStat(**s) for s in payload.get("stats", [])
            ],
            team_comps=[
                TeamComp(
                    brawler_slugs=tuple(c["brawler_slugs"]),  # type: ignore[arg-type]
                    winrate=c["winrate"],
                    sample_size=c.get("sample_size"),
                )
                for c in payload.get("team_comps", [])
            ],
            scraped_at=datetime.fromisoformat(payload["scraped_at"]),
        )


# ----------------------------------------------------------------- helpers


def _as_fraction(value: Any) -> float:
    """Convierte '54.3%', 54.3, 0.543 → 0.543."""
    if value is None:
        return 0.0
    if isinstance(value, str):
        return _parse_percent(value)
    v = float(value)
    return v / 100.0 if v > 1.0 else v


def _as_fraction_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return _as_fraction(value)


def _as_int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_percent(text: str) -> float:
    cleaned = text.strip().replace("%", "").replace(",", ".")
    try:
        v = float(cleaned)
    except ValueError:
        return 0.0
    return v / 100.0 if v > 1.0 else v
