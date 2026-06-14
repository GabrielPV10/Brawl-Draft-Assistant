"""Smoke test end-to-end del backend de Fase 1.

Comprueba que:
  - /health responde
  - /recommend/dummy devuelve top 3
  - el motor de scoring corre sin estallar contra una BD sembrada con datos sintéticos

Uso:
    python -m scripts.smoke_test
    python -m scripts.smoke_test --url http://localhost:8000
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import httpx


async def smoke(base_url: str) -> int:
    failures = 0
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        # /health
        try:
            r = await client.get("/health")
            r.raise_for_status()
            assert r.json().get("status") == "ok", r.json()
            print(f"OK    GET /health -> {r.json()}")
        except Exception as e:
            failures += 1
            print(f"FAIL  GET /health -> {e}")

        # /recommend/dummy
        try:
            r = await client.get("/recommend/dummy")
            r.raise_for_status()
            body = r.json()
            assert len(body["recommendations"]) == 3
            print(
                f"OK    GET /recommend/dummy -> top {len(body['recommendations'])}"
                f" en {body['computed_in_ms']} ms"
            )
        except Exception as e:
            failures += 1
            print(f"FAIL  GET /recommend/dummy -> {e}")

        # /recommend (puede devolver lista vacía si la BD no está sembrada, pero
        # debe responder 200 igual)
        try:
            payload = {
                "map_id": 15040002,
                "phase": "first_pick",
                "allies": [],
                "enemies": [],
                "bans": [],
                "top_n": 3,
            }
            r = await client.post("/recommend", json=payload)
            r.raise_for_status()
            body = r.json()
            print(
                f"OK    POST /recommend (BD) -> {len(body['recommendations'])}"
                f" candidatos en {body['computed_in_ms']} ms"
            )
            if not body["recommendations"]:
                print(
                    "      (lista vacía: corre `python -m scripts.seed_catalog`"
                    " y `python -m scrapers.run_daily` para poblar)"
                )
        except Exception as e:
            failures += 1
            print(f"FAIL  POST /recommend -> {e}")

    return failures


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    args = parser.parse_args()
    sys.exit(asyncio.run(smoke(args.url)))
