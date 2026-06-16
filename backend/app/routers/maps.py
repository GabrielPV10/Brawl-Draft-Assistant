from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.map import Map

router = APIRouter(prefix="/maps", tags=["maps"])

# Modos 3v3 competitivos (excluye Showdown, 5v5, eventos especiales).
COMPETITIVE_MODES = frozenset({
    "Gem Grab", "Brawl Ball", "Heist", "Hot Zone",
    "Knockout", "Bounty", "Wipeout",
})


class MapDto(BaseModel):
    id: int
    name: str
    slug: str
    game_mode: str


class ModeMaps(BaseModel):
    mode: str
    maps: list[MapDto]


@router.get("/catalog", response_model=list[ModeMaps])
def maps_catalog(db: Session = Depends(get_db)) -> list[ModeMaps]:
    """Catálogo de mapas competitivos agrupados por modo de juego.

    Sirve para el selector en cascada (modo → mapa) de la app. Deduplica por
    nombre dentro de cada modo (las rotaciones repiten el mismo mapa con IDs
    distintos; nos quedamos con uno).
    """
    rows = db.execute(
        select(Map)
        .where(Map.game_mode.in_(COMPETITIVE_MODES))
        .order_by(Map.game_mode, Map.name)
    ).scalars().all()

    grouped: dict[str, list[MapDto]] = {}
    seen: set[tuple[str, str]] = set()
    for r in rows:
        key = (r.game_mode, r.name)
        if key in seen:
            continue
        seen.add(key)
        grouped.setdefault(r.game_mode, []).append(
            MapDto(id=r.id, name=r.name, slug=r.slug, game_mode=r.game_mode)
        )
    return [ModeMaps(mode=mode, maps=maps) for mode, maps in sorted(grouped.items())]


@router.get("/search", response_model=list[MapDto])
def search_maps(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> list[MapDto]:
    """Búsqueda de mapas competitivos 3v3 por nombre (case-insensitive, parcial)."""
    term = f"%{q.strip()}%"
    rows = db.execute(
        select(Map)
        .where(
            Map.name.ilike(term),
            Map.game_mode.in_(COMPETITIVE_MODES),
        )
        .order_by(Map.name, Map.game_mode)
        .limit(15)
    ).scalars().all()

    # Deduplica por (name, game_mode): muestra el ID más reciente de cada rotación.
    seen: set[tuple[str, str]] = set()
    result: list[MapDto] = []
    for r in rows:
        key = (r.name, r.game_mode)
        if key not in seen:
            seen.add(key)
            result.append(MapDto(id=r.id, name=r.name, slug=r.slug, game_mode=r.game_mode))
    return result
