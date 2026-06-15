"""Fuente de estadísticas SINTÉTICA. Implementa MapStatsSource + CounterStatsSource.

No toca la red ni la BD: genera datos plausibles y DETERMINISTAS para poder
construir y validar todo el pipeline (ingesta -> BD -> scoring) sin depender de
ninguna fuente real. Es el "mocks primero" del plan, ahora como objeto
sustituible (LSP) en lugar de fixtures sueltas.

Determinismo: el mismo `map_slug` produce siempre las mismas winrates, porque la
semilla del RNG se deriva con hashlib de los identificadores (no de `hash()`, que
Python saltea por proceso). Así los tests y las corridas son reproducibles.
"""

from __future__ import annotations

import hashlib
import random

from scrapers.sources.base import (
    BrawlerMapStat,
    CounterStat,
    MapScrapeResult,
    TeamComp,
)

# Roster real (slugs en el mismo formato que produce scripts.seed_catalog._slugify),
# para que run_daily encuentre el brawler_id al hacer el join contra la BD sembrada.
ROSTER: tuple[str, ...] = (
    "8-bit", "alli", "amber", "angelo", "ash", "barley", "bea", "belle",
    "berry", "bibi", "bo", "bolt", "bonnie", "brock", "bull", "buster",
    "buzz", "buzz-lightyear", "byron", "carl", "charlie", "chester", "chuck",
    "clancy", "colette", "colt", "cordelius", "crow", "damian", "darryl",
    "doug", "draco", "dynamike", "edgar", "el-primo", "emz", "eve", "fang",
    "finx", "frank", "gale", "gene", "gigi", "glowy", "gray", "griff",
    "grom", "gus", "hank", "jacky", "jae-yong", "janet", "jessie", "juju",
    "kaze", "kenji", "kit", "larry-and-lawrie", "leon", "lily", "lola",
    "lou", "lumi", "maisie", "mandy", "max", "meeple", "meg", "melodie",
    "mico", "mina", "moe", "mortis", "mr-p", "najia", "nani", "nita",
    "ollie", "otis", "pam", "pearl", "penny", "pierce", "piper", "poco",
    "rico", "rosa", "r-t", "ruffs", "sam", "sandy", "shade", "shelly",
    "sirius", "spike", "sprout", "squeak", "starr-nova", "stu", "surge",
    "tara", "tick", "trunk", "willow", "ziggy",
)


def _rng(*parts: str) -> random.Random:
    """RNG determinista sembrado con SHA-256 de las partes (estable entre procesos)."""
    digest = hashlib.sha256("|".join(parts).encode()).digest()
    seed = int.from_bytes(digest[:8], "big")
    return random.Random(seed)


def _round(value: float, ndigits: int = 4) -> float:
    return round(value, ndigits)


class MockStatsSource:
    """Datos sintéticos reproducibles. Cumple MapStatsSource y CounterStatsSource."""

    def __init__(self, roster: tuple[str, ...] = ROSTER) -> None:
        self._roster = roster

    # -------------------------------------------------------- MapStatsSource

    async def fetch_map(self, map_slug: str) -> MapScrapeResult:
        """Genera stats por brawler + team comps para `map_slug`.

        Un subconjunto del roster, distinto por mapa, recibe un "boost de meta"
        para que cada mapa tenga sus propios brawlers fuertes (ranking realista).
        """
        meta = self._map_meta_brawlers(map_slug)
        stats = [self._brawler_stat(map_slug, slug, slug in meta) for slug in self._roster]
        team_comps = self._team_comps(map_slug, meta)
        return MapScrapeResult(map_slug=map_slug, stats=stats, team_comps=team_comps)

    def _map_meta_brawlers(self, map_slug: str) -> frozenset[str]:
        """~6 brawlers fuertes en este mapa, elegidos de forma determinista."""
        rng = _rng("meta", map_slug)
        k = min(6, len(self._roster))
        return frozenset(rng.sample(list(self._roster), k))

    def _brawler_stat(self, map_slug: str, slug: str, is_meta: bool) -> BrawlerMapStat:
        rng = _rng("stat", map_slug, slug)
        # Winrate centrada en 0.50; los meta suben, el resto ronda la media.
        base = rng.gauss(0.515 if is_meta else 0.485, 0.025)
        winrate = _round(min(0.65, max(0.38, base)))
        # Pickrate sesgada: los meta se pickean más.
        pick_base = rng.uniform(0.06, 0.22) if is_meta else rng.uniform(0.005, 0.08)
        pickrate = _round(pick_base)
        use_rate = _round(min(0.30, pickrate * rng.uniform(1.0, 1.4)))
        sample = rng.randint(2000, 50000)
        return BrawlerMapStat(
            brawler_slug=slug,
            winrate=winrate,
            pickrate=pickrate,
            use_rate=use_rate,
            sample_size=sample,
        )

    def _team_comps(self, map_slug: str, meta: frozenset[str]) -> list[TeamComp]:
        """8 comps de 3 brawlers, sesgadas hacia los meta del mapa.

        run_daily las descompone en sinergias (score = winrate_comp - 0.5), así
        que las hacemos terminar por encima de 0.5 para sinergias positivas.
        """
        rng = _rng("comps", map_slug)
        pool = list(meta) + [b for b in self._roster if b not in meta]
        weights = [3.0 if b in meta else 1.0 for b in pool]
        comps: list[TeamComp] = []
        seen: set[frozenset[str]] = set()
        attempts = 0
        while len(comps) < 8 and attempts < 50:
            attempts += 1
            trio = tuple(_weighted_sample(rng, pool, weights, 3))
            key = frozenset(trio)
            if len(key) < 3 or key in seen:
                continue
            seen.add(key)
            winrate = _round(min(0.66, max(0.50, rng.gauss(0.555, 0.03))))
            comps.append(
                TeamComp(
                    brawler_slugs=trio,  # type: ignore[arg-type]
                    winrate=winrate,
                    sample_size=rng.randint(500, 12000),
                )
            )
        return comps

    # ---------------------------------------------------- CounterStatsSource

    async def fetch_counters(self) -> list[CounterStat]:
        """Matriz GLOBAL de counters, antisimétrica: score(a→b) = -score(b→a).

        Genera una relación por cada par no ordenado del roster y emite las dos
        direcciones con signo opuesto, para que _counter_score y _counterable
        del motor tengan datos coherentes.
        """
        out: list[CounterStat] = []
        roster = list(self._roster)
        for i, a in enumerate(roster):
            for b in roster[i + 1 :]:
                rng = _rng("counter", a, b)
                # Mayoría de pares neutros, algunos con counter marcado.
                magnitude = rng.uniform(0.0, 0.30)
                if rng.random() < 0.45:  # ~45% de los pares tienen relación notable
                    score = _round(magnitude if rng.random() < 0.5 else -magnitude)
                else:
                    score = _round(rng.uniform(-0.05, 0.05))
                sample = rng.randint(800, 20000)
                out.append(CounterStat(winner_slug=a, loser_slug=b, score=score, sample_size=sample))
                out.append(CounterStat(winner_slug=b, loser_slug=a, score=_round(-score), sample_size=sample))
        return out


def _weighted_sample(
    rng: random.Random, population: list[str], weights: list[float], k: int
) -> list[str]:
    """Muestreo SIN reemplazo ponderado (random.sample no acepta pesos)."""
    pool = list(population)
    w = list(weights)
    picked: list[str] = []
    for _ in range(min(k, len(pool))):
        idx = rng.choices(range(len(pool)), weights=w, k=1)[0]
        picked.append(pool.pop(idx))
        w.pop(idx)
    return picked
