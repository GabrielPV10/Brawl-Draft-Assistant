from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.team import TeamProficiencyRequest, TeamProficiencyResponse
from app.services.supercell import SupercellClient

router = APIRouter(prefix="/team", tags=["team"])


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
