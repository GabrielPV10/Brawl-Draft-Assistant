"""Fuente de estadísticas desde archivo JSON local (generado por scrape_brawlify_playwright).

Compatible con MapStatsSource y CounterStatsSource.
Lee data/map_stats_raw.json y lo convierte al mismo formato que MockStatsSource,
así run_daily.py no necesita cambios — solo cambia el stats_source.

El archivo JSON tiene el formato:
[
  {
    "map_id": 15000710,
    "map_name": "Beach Ball",
    "map_hash": "Beach-Ball",
    "map_mode": "Brawl Ball",
    "brawler_stats": [
      {"brawler_slug": "crow", "winrate": 0.543, "pickrate": 0.112, "sample_size": 12000},
      ...
    ],
    "team_comps": [
      {"brawler_slugs": ["crow", "edgar", "gale"], "winrate": 0.58, "sample_size": 500},
      ...
    ]
  },
  ...
]
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from scrapers.sources.base import BrawlerMapStat, CounterStat, MapScrapeResult, TeamComp

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).parent.parent.parent / "data" / "map_stats_raw.json"


def _slugify(name: str) -> str:
    return name.strip().lower().replace("'", "").replace(".", "").replace("&", "and").replace(" ", "-")


class JsonFileStatsSource:
    """Lee stats reales pre-scrapeados de un archivo JSON local.

    Implementa MapStatsSource (misma interfaz que MockStatsSource y BrawlifyStatsSource).
    No implementa CounterStatsSource — los counters se curan por separado.
    """

    def __init__(self, path: Path = DEFAULT_PATH) -> None:
        self._path = path
        self._index: dict[str, dict[str, Any]] | None = None

    def _load(self) -> dict[str, dict[str, Any]]:
        if self._index is not None:
            return self._index
        if not self._path.exists():
            raise FileNotFoundError(
                f"Archivo de stats no encontrado: {self._path}\n"
                "Ejecuta primero: python -m scripts.scrape_brawlify_playwright"
            )
        with open(self._path, encoding="utf-8") as f:
            raw: list[dict[str, Any]] = json.load(f)

        # Indexa por slug (igual que lo que guarda seed_catalog).
        index: dict[str, dict[str, Any]] = {}
        for entry in raw:
            slug = _slugify(entry.get("map_name", entry.get("map_hash", "")))
            index[slug] = entry
        self._index = index
        logger.info("JsonFileStatsSource: %d mapas cargados desde %s", len(index), self._path)
        return index

    async def fetch_map(self, map_slug: str) -> MapScrapeResult:
        index = self._load()
        entry = index.get(map_slug.lower())
        if entry is None:
            logger.debug("Sin datos JSON para mapa '%s' — stats vacías", map_slug)
            return MapScrapeResult(map_slug=map_slug, stats=[], team_comps=[])

        stats = [
            BrawlerMapStat(
                brawler_slug=s["brawler_slug"],
                winrate=float(s.get("winrate") or 0.0),
                pickrate=float(s.get("pickrate") or 0.0),
                use_rate=None,
                sample_size=s.get("sample_size"),
            )
            for s in entry.get("brawler_stats", [])
            if s.get("brawler_slug")
        ]

        team_comps = [
            TeamComp(
                brawler_slugs=tuple(c["brawler_slugs"]),
                winrate=float(c.get("winrate") or 0.5),
                sample_size=c.get("sample_size"),
            )
            for c in entry.get("team_comps", [])
            if len(c.get("brawler_slugs", [])) >= 3
        ]

        return MapScrapeResult(map_slug=map_slug, stats=stats, team_comps=team_comps)
