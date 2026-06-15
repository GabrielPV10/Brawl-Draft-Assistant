from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.brawler import Brawler

router = APIRouter(prefix="/brawlers", tags=["brawlers"])


class BrawlerDto(BaseModel):
    id: int
    name: str
    slug: str


@router.get("/search", response_model=list[BrawlerDto])
def search_brawlers(
    q: str = Query(..., min_length=1, description="Nombre o slug del brawler"),
    db: Session = Depends(get_db),
) -> list[BrawlerDto]:
    """Busca brawlers por nombre o slug (case-insensitive, coincidencia parcial).

    Usado por la app Android para resolver 'shelly' → id=16000000.
    """
    term = f"%{q.lower().strip()}%"
    rows = db.execute(
        select(Brawler).where(
            Brawler.slug.ilike(term) | Brawler.name.ilike(term)
        ).limit(10)
    ).scalars().all()
    return [BrawlerDto(id=r.id, name=r.name, slug=r.slug) for r in rows]


@router.get("", response_model=list[BrawlerDto])
def list_brawlers(db: Session = Depends(get_db)) -> list[BrawlerDto]:
    """Lista completa de brawlers (para autocompletar en la app)."""
    rows = db.execute(select(Brawler).order_by(Brawler.name)).scalars().all()
    return [BrawlerDto(id=r.id, name=r.name, slug=r.slug) for r in rows]
