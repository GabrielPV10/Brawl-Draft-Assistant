from enum import Enum

from pydantic import BaseModel, Field


class DraftPhase(str, Enum):
    FIRST_PICK = "first_pick"
    MID_PICKS = "mid_picks"
    LAST_PICK = "last_pick"


class DraftRequest(BaseModel):
    """Payload que envía Android al endpoint POST /recommend."""

    map_id: int = Field(..., description="ID del mapa del catálogo BrawlAPI.")
    game_mode: str | None = Field(None, description="Modo (Knockout, BrawlBall, etc).")
    phase: DraftPhase
    allies: list[int] = Field(
        default_factory=list, description="IDs de brawlers ya pickeados por mi equipo."
    )
    enemies: list[int] = Field(
        default_factory=list, description="IDs de brawlers ya pickeados por el rival."
    )
    bans: list[int] = Field(default_factory=list, description="IDs baneados.")

    # Si el usuario tiene el perfil del equipo cargado, manda el profile_id
    profile_id: int | None = Field(
        None, description="Si se pasa, las recomendaciones se personalizan por miembro."
    )
    # Slot para el cual se está recomendando (0=tú, 1=cuate1, 2=cuate2)
    slot: int | None = Field(None, ge=0, le=2)

    top_n: int = Field(3, ge=1, le=10)


class DraftRecommendation(BaseModel):
    brawler_id: int
    brawler_name: str
    score: float
    breakdown: dict[str, float] = Field(
        default_factory=dict,
        description="Aporte de cada factor (winrate_mapa, counter_score, etc).",
    )
    explanation: str | None = Field(None, description="Explicación generada por LLM (Fase 5).")


class DraftResponse(BaseModel):
    map_id: int
    phase: DraftPhase
    recommendations: list[DraftRecommendation]
    computed_in_ms: int
