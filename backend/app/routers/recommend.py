import time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.draft import DraftRecommendation, DraftRequest, DraftResponse
from app.services.scoring import ScoringEngine

router = APIRouter(prefix="/recommend", tags=["recommend"])


@router.post("", response_model=DraftResponse)
async def recommend(req: DraftRequest, db: Session = Depends(get_db)) -> DraftResponse:
    """Devuelve el top N de brawlers recomendados para la fase actual del draft.

    Stub: por ahora retorna recomendaciones dummy. El cálculo real vivirá en
    ScoringEngine.score_candidates() una vez que el scraper de Brawlify pueble map_stats.
    """
    started = time.perf_counter()
    engine = ScoringEngine(db)
    candidates = engine.score_candidates(req)
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    return DraftResponse(
        map_id=req.map_id,
        phase=req.phase,
        recommendations=candidates[: req.top_n],
        computed_in_ms=elapsed_ms,
    )


@router.get("/dummy", response_model=DraftResponse)
async def recommend_dummy() -> DraftResponse:
    """Endpoint dummy para que la app Android pueda probar la integración sin BD."""
    return DraftResponse(
        map_id=1,
        phase="first_pick",  # type: ignore[arg-type]
        recommendations=[
            DraftRecommendation(
                brawler_id=16000000,
                brawler_name="Piper",
                score=87.5,
                breakdown={"winrate_mapa": 0.58, "pickrate_relativo": 0.32},
                explanation="Stub: alta winrate en este mapa y bajo ban risk.",
            ),
            DraftRecommendation(
                brawler_id=16000037,
                brawler_name="Bonnie",
                score=84.2,
                breakdown={"winrate_mapa": 0.61, "counterable": -0.20},
                explanation="Stub: meta fuerte pero countereable, mejor para mid pick.",
            ),
            DraftRecommendation(
                brawler_id=16000054,
                brawler_name="Mandy",
                score=80.1,
                breakdown={"winrate_mapa": 0.55, "sinergia": 0.18},
                explanation="Stub: control de área sólido.",
            ),
        ],
        computed_in_ms=0,
    )
