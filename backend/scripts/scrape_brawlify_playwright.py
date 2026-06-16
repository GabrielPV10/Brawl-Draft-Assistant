"""Scraper LOCAL de Brawlify usando Playwright (bypassa Cloudflare).

Corre UNA VEZ en tu computadora. Guarda los stats reales en data/map_stats_raw.json.
Después ejecutas `python -m scrapers.run_daily` con STATS_SOURCE=json para subir a Neon.

Instalación (una sola vez):
    pip install playwright
    playwright install chromium

Uso:
    python -m scripts.scrape_brawlify_playwright
    python -m scripts.scrape_brawlify_playwright --limit 5   # solo primeros 5 mapas (prueba)
    python -m scripts.scrape_brawlify_playwright --out data/mis_stats.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BRAWLAPI_BASE = "https://api.brawlapi.com/v1"
BRAWLIFY_BASE = "https://brawlify.com"
OUT_DEFAULT = Path(__file__).parent.parent / "data" / "map_stats_raw.json"

# Modos competitivos 3v3 que nos interesan (nombre exacto de Brawlify).
COMPETITIVE_MODES: frozenset[str] = frozenset({
    "Gem Grab", "Brawl Ball", "Heist", "Hot Zone",
    "Knockout", "Bounty", "Wipeout",
})


async def fetch_competitive_maps() -> list[dict[str, Any]]:
    """Devuelve todos los mapas competitivos desde BrawlAPI (sin stats, solo metadatos)."""
    async with httpx.AsyncClient(base_url=BRAWLAPI_BASE, timeout=20.0) as client:
        resp = await client.get("/maps")
        resp.raise_for_status()
    maps = resp.json().get("list", [])

    result: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    for m in maps:
        mode = (m.get("gameMode") or {})
        mode_name = mode.get("name", "") if isinstance(mode, dict) else str(mode)
        if mode_name not in COMPETITIVE_MODES:
            continue
        if not m.get("hash"):
            continue
        h = m["hash"]
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        result.append({
            "id": m["id"],
            "name": m["name"],
            "hash": h,
            "mode": mode_name,
        })
    return result


def _extract_next_data(html: str) -> dict[str, Any] | None:
    match = re.search(r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _parse_stats(map_hash: str, next_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extrae la lista de brawler stats del JSON embebido por Next.js."""
    page_props = next_data.get("props", {}).get("pageProps", {})
    stats_raw = page_props.get("stats") or page_props.get("brawlerStats") or []
    team_comps_raw = page_props.get("teamComps") or page_props.get("compositions") or []

    def _frac(v: Any) -> float:
        if v is None:
            return 0.0
        if isinstance(v, str):
            cleaned = v.replace("%", "").strip()
            try:
                f = float(cleaned)
            except ValueError:
                return 0.0
            return f / 100.0 if f > 1.0 else f
        f = float(v)
        return f / 100.0 if f > 1.0 else f

    brawler_stats = []
    for s in stats_raw:
        slug = s.get("brawler") or s.get("slug") or s.get("name") or ""
        if not slug:
            continue
        brawler_stats.append({
            "brawler_slug": str(slug).lower().replace(" ", "-").replace("'", ""),
            "winrate": _frac(s.get("winRate") or s.get("winrate")),
            "pickrate": _frac(s.get("pickRate") or s.get("pickrate")),
            "sample_size": s.get("samples") or s.get("sampleSize"),
        })

    team_comps = []
    for c in team_comps_raw:
        brawlers = c.get("brawlers") or c.get("comp") or []
        if len(brawlers) < 3:
            continue
        team_comps.append({
            "brawler_slugs": [str(b).lower().replace(" ", "-") for b in brawlers[:3]],
            "winrate": _frac(c.get("winRate") or c.get("winrate")),
            "sample_size": c.get("samples") or c.get("sampleSize"),
        })

    return brawler_stats, team_comps


async def scrape_map(page, map_info: dict[str, Any]) -> dict[str, Any] | None:
    """Visita la página de un mapa en Brawlify y extrae sus stats."""
    url = f"{BRAWLIFY_BASE}/maps/detail/{map_info['hash']}"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        # Espera a que Next.js inyecte __NEXT_DATA__ (ya está en HTML inicial, pero por si acaso)
        await page.wait_for_selector("#__NEXT_DATA__", timeout=10_000)
        html = await page.content()
    except Exception as e:
        logger.warning("No se pudo cargar %s: %s", url, e)
        return None

    next_data = _extract_next_data(html)
    if next_data is None:
        logger.warning("Sin __NEXT_DATA__ en %s", map_info["name"])
        return None

    brawler_stats, team_comps = _parse_stats(map_info["hash"], next_data)
    if not brawler_stats:
        logger.warning("Stats vacías para %s (puede que Cloudflare bloqueó)", map_info["name"])
        return None

    logger.info("✓ %s (%s): %d brawlers, %d comps", map_info["name"], map_info["mode"], len(brawler_stats), len(team_comps))
    return {
        "map_id": map_info["id"],
        "map_name": map_info["name"],
        "map_hash": map_info["hash"],
        "map_mode": map_info["mode"],
        "brawler_stats": brawler_stats,
        "team_comps": team_comps,
    }


async def main(limit: int | None, out: Path) -> None:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ERROR: playwright no está instalado.")
        print("Ejecuta: pip install playwright && playwright install chromium")
        sys.exit(1)

    logger.info("Obteniendo lista de mapas competitivos desde BrawlAPI…")
    maps = await fetch_competitive_maps()
    if limit:
        maps = maps[:limit]
    logger.info("%d mapas a scrapear", len(maps))

    results = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="en-US",
        )
        page = await context.new_page()

        for i, m in enumerate(maps, 1):
            logger.info("[%d/%d] Scrapeando %s…", i, len(maps), m["name"])
            result = await scrape_map(page, m)
            if result:
                results.append(result)
            # Pequeña pausa para no saturar el servidor
            await asyncio.sleep(1.5)

        await browser.close()

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info("Guardado en %s — %d/%d mapas con datos", out, len(results), len(maps))
    if len(results) < len(maps):
        logger.warning("%d mapas sin datos (probablemente Cloudflare). Revisa manualmente.", len(maps) - len(results))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Scraper local de Brawlify con Playwright")
    parser.add_argument("--limit", type=int, default=None, help="Limita a N mapas (para prueba)")
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT, help="Archivo JSON de salida")
    args = parser.parse_args()
    asyncio.run(main(args.limit, args.out))
