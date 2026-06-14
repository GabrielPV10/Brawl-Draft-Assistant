"""Job programado: refresca map_stats y synergies para todos los mapas competitivos.

Uso:
    python -m scrapers.run_daily
    python -m scrapers.run_daily --map gem-grab-undermine

Pensado para correr en cron cada 6 horas. Idempotente: usa upserts y la próxima
corrida termina lo pendiente si una request falla.
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import SessionLocal, engine
from app.models.brawler import Brawler
from app.models.map import Map
from app.models.map_stats import MapStats
from app.models.synergy import Synergy
from scrapers.brawlify_scraper import BrawlifyStatsSource
from scrapers.sources.base import MapScrapeResult

logger = logging.getLogger("scrapers.run_daily")


async def run(map_slug: str | None = None) -> None:
    scraper = BrawlifyStatsSource()
    map_slugs = [map_slug] if map_slug else _load_map_slugs()
    if not map_slugs:
        logger.warning("No hay mapas sembrados. Corre `python -m scripts.seed_catalog` primero.")
        return

    total_stats = 0
    total_synergies = 0
    for slug in map_slugs:
        try:
            res = await scraper.fetch_map(slug)
        except Exception:
            logger.exception("Fallo scrapeando %s", slug)
            continue

        s, sy = _persist(res)
        total_stats += s
        total_synergies += sy
        logger.info(
            "Scrapeado %s: %d stats, %d sinergias", slug, len(res.stats), len(res.team_comps)
        )

    logger.info(
        "Done. %d mapas procesados, %d filas map_stats, %d filas synergies.",
        len(map_slugs),
        total_stats,
        total_synergies,
    )


def _load_map_slugs() -> list[str]:
    with SessionLocal() as db:
        return [row.slug for row in db.execute(select(Map)).scalars().all()]


def _slug_to_brawler_id(db) -> dict[str, int]:
    return {row.slug.lower(): row.id for row in db.execute(select(Brawler)).scalars().all()}


def _slug_to_map_id(db) -> dict[str, int]:
    return {row.slug.lower(): row.id for row in db.execute(select(Map)).scalars().all()}


def _persist(res: MapScrapeResult) -> tuple[int, int]:
    """Upsert map_stats y synergies. Devuelve (filas_stats, filas_synergies)."""
    if not res.stats and not res.team_comps:
        return 0, 0

    with SessionLocal() as db:
        brawler_ids = _slug_to_brawler_id(db)
        map_ids = _slug_to_map_id(db)
        map_id = map_ids.get(res.map_slug.lower())
        if map_id is None:
            logger.warning(
                "Mapa %s no está en la BD; corre seed_catalog antes.", res.map_slug
            )
            return 0, 0

        stats_count = _upsert_map_stats(db, map_id, brawler_ids, res)
        synergy_count = _upsert_team_comps_as_synergies(db, map_id, brawler_ids, res)
        db.commit()
        return stats_count, synergy_count


def _upsert_map_stats(
    db, map_id: int, brawler_ids: dict[str, int], res: MapScrapeResult
) -> int:
    payloads = []
    for s in res.stats:
        bid = brawler_ids.get(s.brawler_slug.lower())
        if bid is None:
            continue
        payloads.append(
            {
                "map_id": map_id,
                "brawler_id": bid,
                "winrate": s.winrate,
                "pickrate": s.pickrate,
                "use_rate": s.use_rate,
                "sample_size": s.sample_size,
            }
        )
    if not payloads:
        return 0

    if engine.dialect.name == "postgresql":
        stmt = pg_insert(MapStats).values(payloads)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_map_stats_map_brawler",
            set_={
                "winrate": stmt.excluded.winrate,
                "pickrate": stmt.excluded.pickrate,
                "use_rate": stmt.excluded.use_rate,
                "sample_size": stmt.excluded.sample_size,
            },
        )
        db.execute(stmt)
    else:
        for p in payloads:
            existing = db.execute(
                select(MapStats).where(
                    MapStats.map_id == p["map_id"], MapStats.brawler_id == p["brawler_id"]
                )
            ).scalar_one_or_none()
            if existing is None:
                db.add(MapStats(**p))
            else:
                for k, v in p.items():
                    setattr(existing, k, v)
    return len(payloads)


def _upsert_team_comps_as_synergies(
    db, map_id: int, brawler_ids: dict[str, int], res: MapScrapeResult
) -> int:
    """Cada team comp de 3 brawlers se descompone en 3 pares de sinergia.

    La score de sinergia entre (a, b) es la winrate de la comp menos 0.5
    (centrada en 0). Se hace upsert por (b1, b2, map_id, 'synergy').
    """
    pair_scores: dict[tuple[int, int], list[float]] = {}
    for c in res.team_comps:
        ids = [brawler_ids.get(s.lower()) for s in c.brawler_slugs]
        if any(i is None for i in ids):
            continue
        a, b, d = ids  # type: ignore[misc]
        score = c.winrate - 0.5
        for x, y in ((a, b), (a, d), (b, d)):
            pair_scores.setdefault((x, y), []).append(score)
            pair_scores.setdefault((y, x), []).append(score)

    if not pair_scores:
        return 0

    payloads = [
        {
            "b1_id": x,
            "b2_id": y,
            "map_id": map_id,
            "relation_type": "synergy",
            "score": sum(scores) / len(scores),
            "sample_size": len(scores),
        }
        for (x, y), scores in pair_scores.items()
    ]

    if engine.dialect.name == "postgresql":
        stmt = pg_insert(Synergy).values(payloads)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_synergy_pair",
            set_={
                "score": stmt.excluded.score,
                "sample_size": stmt.excluded.sample_size,
            },
        )
        db.execute(stmt)
    else:
        for p in payloads:
            existing = db.execute(
                select(Synergy).where(
                    Synergy.b1_id == p["b1_id"],
                    Synergy.b2_id == p["b2_id"],
                    Synergy.map_id == p["map_id"],
                    Synergy.relation_type == p["relation_type"],
                )
            ).scalar_one_or_none()
            if existing is None:
                db.add(Synergy(**p))
            else:
                existing.score = p["score"]
                existing.sample_size = p["sample_size"]
    return len(payloads)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", dest="map_slug", default=None, help="Slug específico a scrapear")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    asyncio.run(run(args.map_slug))
