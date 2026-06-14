"""Siembra brawlers y mapas desde BrawlAPI.

Uso:
    python -m scripts.seed_catalog
    python -m scripts.seed_catalog --only brawlers
    python -m scripts.seed_catalog --only maps

Idempotente: usa INSERT ... ON CONFLICT DO UPDATE para no duplicar.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Any

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import SessionLocal, engine
from app.models.brawler import Brawler
from app.models.map import Map

logger = logging.getLogger("scripts.seed_catalog")

BRAWLAPI_BASE = "https://api.brawlapi.com/v1"
COMPETITIVE_MODES = {
    "knockout",
    "brawlBall",
    "bounty",
    "gemGrab",
    "heist",
    "hotZone",
    "wipeout",
    "brawlBall5v5",
}


async def fetch_brawlers() -> list[dict[str, Any]]:
    async with httpx.AsyncClient(base_url=BRAWLAPI_BASE, timeout=20.0) as client:
        resp = await client.get("/brawlers")
        resp.raise_for_status()
        return resp.json().get("list", [])


async def fetch_maps() -> list[dict[str, Any]]:
    async with httpx.AsyncClient(base_url=BRAWLAPI_BASE, timeout=20.0) as client:
        resp = await client.get("/maps")
        resp.raise_for_status()
        return resp.json().get("list", [])


def upsert_brawlers(rows: list[dict[str, Any]]) -> int:
    dialect = engine.dialect.name
    payloads = [
        {
            "id": r["id"],
            "name": r["name"],
            "slug": _slugify(r["name"]),
            "rarity": (r.get("rarity") or {}).get("name"),
            "class_name": (r.get("class") or {}).get("name"),
            "icon_url": r.get("imageUrl") or r.get("imageUrl2"),
        }
        for r in rows
        if "id" in r and "name" in r
    ]
    if not payloads:
        return 0

    with SessionLocal() as db:
        if dialect == "postgresql":
            stmt = pg_insert(Brawler).values(payloads)
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "name": stmt.excluded.name,
                    "slug": stmt.excluded.slug,
                    "rarity": stmt.excluded.rarity,
                    "class_name": stmt.excluded.class_name,
                    "icon_url": stmt.excluded.icon_url,
                },
            )
            db.execute(stmt)
        else:
            for p in payloads:
                existing = db.get(Brawler, p["id"])
                if existing is None:
                    db.add(Brawler(**p))
                else:
                    for k, v in p.items():
                        setattr(existing, k, v)
        db.commit()
    return len(payloads)


def upsert_maps(rows: list[dict[str, Any]]) -> int:
    dialect = engine.dialect.name
    payloads = []
    for r in rows:
        mode = (r.get("gameMode") or {}).get("name") or r.get("gameMode") or ""
        if isinstance(mode, dict):
            mode = mode.get("name", "")
        if not r.get("id") or not r.get("name"):
            continue
        payloads.append(
            {
                "id": r["id"],
                "name": r["name"],
                "slug": _slugify(r["name"]),
                "game_mode": str(mode),
                "image_url": r.get("imageUrl"),
            }
        )

    if not payloads:
        return 0

    with SessionLocal() as db:
        if dialect == "postgresql":
            stmt = pg_insert(Map).values(payloads)
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "name": stmt.excluded.name,
                    "slug": stmt.excluded.slug,
                    "game_mode": stmt.excluded.game_mode,
                    "image_url": stmt.excluded.image_url,
                },
            )
            db.execute(stmt)
        else:
            for p in payloads:
                existing = db.get(Map, p["id"])
                if existing is None:
                    db.add(Map(**p))
                else:
                    for k, v in p.items():
                        setattr(existing, k, v)
        db.commit()
    return len(payloads)


def _slugify(name: str) -> str:
    return (
        name.strip()
        .lower()
        .replace("'", "")
        .replace(".", "")
        .replace("&", "and")
        .replace(" ", "-")
    )


async def main(only: str | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if only in (None, "brawlers"):
        brawlers = await fetch_brawlers()
        n = upsert_brawlers(brawlers)
        logger.info("Sembrados %d brawlers", n)
    if only in (None, "maps"):
        maps = await fetch_maps()
        n = upsert_maps(maps)
        logger.info("Sembrados %d maps", n)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=["brawlers", "maps"], default=None)
    args = parser.parse_args()
    asyncio.run(main(args.only))
