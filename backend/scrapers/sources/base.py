"""Contrato de las fuentes de estadísticas de la capa de ingesta.

Aquí viven los DTOs canónicos y las interfaces (Protocols) que cualquier fuente
de datos debe cumplir. El motor de scoring NO depende de esto: lee de la BD ya
materializada. Quien depende del contrato es el job de ingesta (`run_daily`), que
recibe una fuente por inyección y la usa sin saber si es Brawlify, Mock o lo que
venga después (DIP + LSP).

Separamos en dos interfaces pequeñas (ISP) porque los datos tienen dos formas y
dos alcances distintos:

    - `MapStatsSource`     -> datos POR MAPA: winrate/pickrate por brawler y las
                              sinergias derivadas de team comps de ese mapa.
    - `CounterStatsSource` -> matriz GLOBAL de counters (b1 le gana a b2), que no
                              depende del mapa.

Una fuente puede implementar una, otra o ambas. Mock implementa las dos; una
fuente real de solo-mapas implementa únicamente `MapStatsSource`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable

# --------------------------------------------------------------------- DTOs


@dataclass
class BrawlerMapStat:
    """Rendimiento de un brawler en un mapa concreto. Rates en fracción 0.0-1.0."""

    brawler_slug: str
    winrate: float
    pickrate: float
    use_rate: float | None = None
    sample_size: int | None = None


@dataclass
class TeamComp:
    """Composición de 3 brawlers que jugaron juntos y su winrate como equipo."""

    brawler_slugs: tuple[str, str, str]
    winrate: float
    sample_size: int | None = None


@dataclass
class CounterStat:
    """Relación de counter GLOBAL: `winner_slug` le gana a `loser_slug`.

    `score` está centrado en 0: positivo = ventaja del winner sobre el loser,
    negativo = desventaja. Rango esperado -1.0 a 1.0.
    """

    winner_slug: str
    loser_slug: str
    score: float
    sample_size: int | None = None


@dataclass
class MapScrapeResult:
    """Resultado de consultar una fuente para un mapa: stats + team comps."""

    map_slug: str
    stats: list[BrawlerMapStat] = field(default_factory=list)
    team_comps: list[TeamComp] = field(default_factory=list)
    scraped_at: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------- interfaces


@runtime_checkable
class MapStatsSource(Protocol):
    """Fuente de estadísticas por-mapa. Sustituible (LSP) por cualquier impl."""

    async def fetch_map(self, map_slug: str) -> MapScrapeResult:
        """Devuelve las stats y team comps del mapa identificado por `map_slug`.

        No debe lanzar por ausencia de datos: si el mapa no tiene info, devuelve
        un `MapScrapeResult` con listas vacías. Sí puede lanzar por errores de
        transporte (HTTP, timeout) para que el caller decida reintentar.
        """
        ...


@runtime_checkable
class CounterStatsSource(Protocol):
    """Fuente de la matriz GLOBAL de counters entre brawlers."""

    async def fetch_counters(self) -> list[CounterStat]:
        """Devuelve todas las relaciones de counter conocidas (independientes del mapa)."""
        ...
