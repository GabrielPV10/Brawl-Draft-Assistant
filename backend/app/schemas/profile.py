from datetime import datetime

from pydantic import BaseModel, Field, field_validator


def _normalize_tag(tag: str) -> str:
    """Acepta '#ABC123' o 'ABC123', devuelve 'ABC123' en mayúsculas."""
    cleaned = tag.strip().upper().lstrip("#")
    if not cleaned.isalnum():
        raise ValueError(f"player_tag inválido: {tag!r}")
    return cleaned


class ProfileMember(BaseModel):
    slot: int = Field(..., ge=0, le=2)
    player_tag: str
    nickname: str | None = None

    @field_validator("player_tag")
    @classmethod
    def _validate_tag(cls, v: str) -> str:
        return _normalize_tag(v)


class ProfileCreate(BaseModel):
    owner_id: str = Field(..., max_length=128)
    name: str = Field(..., max_length=64)
    members: list[ProfileMember] = Field(..., min_length=1, max_length=3)


class ProfileUpdate(BaseModel):
    name: str | None = Field(None, max_length=64)
    members: list[ProfileMember] | None = None


class ProfileRead(BaseModel):
    id: int
    owner_id: str
    name: str
    members: list[ProfileMember]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
