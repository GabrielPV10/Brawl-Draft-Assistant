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

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.models.brawler import Brawler
from app.models.map import Map
from app.models.map_stats import MapStats
from app.models.synergy import Synergy
from scrapers.brawlify_scraper import BrawlifyStatsSource
from scrapers.sources.base import (
    CounterStatsSource,
    MapScrapeResult,
    MapStatsSource,
)
from scrapers.sources.mock import MockStatsSource

logger = logging.getLogger("scrapers.run_daily")


def make_source() -> MapStatsSource:
    """Construye la fuente de stats según settings.stats_source (wiring DIP).

    El único lugar donde se decide la implementación concreta. run() depende solo
    de la interfaz MapStatsSource, no de la clase concreta.
    """
    name = get_settings().stats_source.lower()
    if name == "mock":
        return MockStatsSource()
    if name == "brawlify":
        return BrawlifyStatsSource()
    raise ValueError(f"stats_source desconocido: {name!r} (usa 'mock' o 'brawlify')")


async def run(map_slug: str | None = None, source: MapStatsSource | None = None) -> None:
    source = source or make_source()
    map_slugs = [map_slug] if map_slug else _load_map_slugs()
    if not map_slugs:
        logger.warning("No hay mapas sembrados. Corre `python -m scripts.seed_catalog` primero.")
        return

    total_stats = 0
    total_synergies = 0
    for slug in map_slugs:
        try:
            res = await source.fetch_map(slug)
        except Exception:
            logger.exception("Fallo obteniendo datos de %s", slug)
            continue

        s, sy = _persist(res)
        total_stats += s
        total_synergies += sy
        logger.info(
            "Procesado %s: %d stats, %d sinergias", slug, len(res.stats), len(res.team_comps)
        )

    # Counters: matriz GLOBAL, se refresca una sola vez por corrida (no por mapa).
    total_counters = 0
    if isinstance(source, CounterStatsSource):
        total_counters = await _refresh_counters(source)

    logger.info(
        "Done. %d mapas, %d filas map_stats, %d sinergias, %d counters.",
        len(map_slugs),
        total_stats,
        total_synergies,
        total_counters,
    )


def _load_map_slugs() -> list[str]:
    with SessionLocal() as db:
        # Deduplica por slug: un slug con varios IDs de rotación solo se fetchea una vez.
        seen: set[str] = set()
        slugs: list[str] = []
        for row in db.execute(select(Map)).scalars().all():
            if row.slug not in seen:
                seen.add(row.slug)
                slugs.append(row.slug)
        return slugs


def _slug_to_brawler_id(db) -> dict[str, int]:
    return {row.slug.lower(): row.id for row in db.execute(select(Brawler)).scalars().all()}


def _slug_to_all_map_ids(db) -> dict[str, list[int]]:
    """Devuelve slug → [id1, id2, …] (un slug puede tener varios IDs de rotación)."""
    result: dict[str, list[int]] = {}
    for row in db.execute(select(Map)).scalars().all():
        result.setdefault(row.slug.lower(), []).append(row.id)
    return result


def _persist(res: MapScrapeResult) -> tuple[int, int]:
    """Upsert map_stats y synergies para todos los IDs que comparten el slug.

    Un mismo slug (ej. 'hard-rock-mine') puede aparecer con varios map_ids en
    la tabla maps (distintas rotaciones). Si solo guardamos para uno, el scoring
    devuelve winrate=0 al buscar por cualquier otro ID. Guardamos para todos.
    """
    if not res.stats and not res.team_comps:
        return 0, 0

    with SessionLocal() as db:
        brawler_ids = _slug_to_brawler_id(db)
        slug_to_ids = _slug_to_all_map_ids(db)
        map_ids = slug_to_ids.get(res.map_slug.lower())
        if not map_ids:
            logger.warning(
                "Mapa %s no está en la BD; corre seed_catalog antes.", res.map_slug
            )
            return 0, 0

        total_stats = 0
        total_synergies = 0
        for map_id in map_ids:
            total_stats += _upsert_map_stats(db, map_id, brawler_ids, res)
            total_synergies += _upsert_team_comps_as_synergies(db, map_id, brawler_ids, res)
        db.commit()
        return total_stats, total_synergies


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


async def _refresh_counters(source: CounterStatsSource) -> int:
    """Reemplaza TODA la matriz de counters (relation_type='counter', map_id NULL).

    Usamos delete-then-insert en vez de upsert a propósito: el UniqueConstraint
    incluye map_id, y en Postgres dos NULL se consideran distintos, así que un
    ON CONFLICT no detectaría el choque y duplicaría filas en cada corrida. Como
    los counters son globales y se regeneran completos, borrar e insertar es la
    estrategia idempotente más simple y correcta.
    """
    counters = await source.fetch_counters()
    if not counters:
        return 0

    with SessionLocal() as db:
        brawler_ids = _slug_to_brawler_id(db)
        rows = []
        for c in counters:
            w = brawler_ids.get(c.winner_slug.lower())
            loser = brawler_ids.get(c.loser_slug.lower())
            if w is None or loser is None:
                continue
            rows.append(
                Synergy(
                    b1_id=w,
                    b2_id=loser,
                    map_id=None,
                    relation_type="counter",
                    score=c.score,
                    sample_size=c.sample_size,
                )
            )
        db.execute(delete(Synergy).where(Synergy.relation_type == "counter"))
        if rows:
            db.add_all(rows)
        db.commit()
        return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", dest="map_slug", default=None, help="Slug específico a scrapear")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    asyncio.run(run(args.map_slug))
