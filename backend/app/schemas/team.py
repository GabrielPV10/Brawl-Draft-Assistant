from pydantic import BaseModel, Field


class BrawlerProficiency(BaseModel):
    brawler_id: int
    brawler_name: str
    proficiency: float = Field(..., ge=0.0, le=100.0)
    trophies: int
    power_level: int
    gadgets_unlocked: int
    star_powers_unlocked: int
    recent_winrate: float | None = None


class PlayerProficiencyReport(BaseModel):
    player_tag: str
    nickname: str | None = None
    brawlers: list[BrawlerProficiency]


class TeamProficiencyRequest(BaseModel):
    player_tags: list[str] = Field(..., min_length=1, max_length=3)


class TeamProficiencyResponse(BaseModel):
    players: list[PlayerProficiencyReport]
    cached: bool = False
