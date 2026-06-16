from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.team import TeamProficiencyRequest, TeamProficiencyResponse
from app.services.scoring import ScoringEngine
from app.services.supercell import SupercellClient

router = APIRouter(prefix="/team", tags=["team"])


class EvaluateRequest(BaseModel):
    map_id: int
    allies: list[int]
    enemies: list[int]


class EvaluateResponse(BaseModel):
    win_probability: float
    our_avg_score: float
    enemy_avg_score: float


@router.post("/evaluate", response_model=EvaluateResponse)
def evaluate_team(req: EvaluateRequest, db: Session = Depends(get_db)) -> EvaluateResponse:
    """Estima la probabilidad de victoria comparando ambos equipos al final del draft."""
    engine = ScoringEngine(db)
    result = engine.evaluate_team(req.map_id, req.allies, req.enemies)
    return EvaluateResponse(**result)


@router.post("/proficiency", response_model=TeamProficiencyResponse)
async def team_proficiency(
    req: TeamProficiencyRequest,
    db: Session = Depends(get_db),
) -> TeamProficiencyResponse:
    """Consulta la API oficial de Supercell para cada player_tag y devuelve
    el reporte de proficiency por brawler. Se cachea en Redis (TTL 1h por jugador)."""
    client = SupercellClient()
    reports = []
    for tag in req.player_tags:
        reports.append(await client.fetch_player_proficiency(tag))
    return TeamProficiencyResponse(players=reports, cached=False)
