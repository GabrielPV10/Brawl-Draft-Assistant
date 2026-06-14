from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.team_profile import MAX_PROFILES_PER_USER, TeamProfile, TeamProfileMember
from app.schemas.profile import ProfileCreate, ProfileRead, ProfileUpdate

router = APIRouter(prefix="/profiles", tags=["profiles"])


def _to_read(profile: TeamProfile) -> ProfileRead:
    return ProfileRead.model_validate(
        {
            "id": profile.id,
            "owner_id": profile.owner_id,
            "name": profile.name,
            "members": [
                {"slot": m.slot, "player_tag": m.player_tag, "nickname": m.nickname}
                for m in profile.members
            ],
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
        }
    )


@router.get("", response_model=list[ProfileRead])
async def list_profiles(owner_id: str, db: Session = Depends(get_db)) -> list[ProfileRead]:
    stmt = (
        select(TeamProfile)
        .where(TeamProfile.owner_id == owner_id)
        .options(selectinload(TeamProfile.members))
        .order_by(TeamProfile.updated_at.desc())
    )
    profiles = db.execute(stmt).scalars().all()
    return [_to_read(p) for p in profiles]


@router.post("", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
async def create_profile(payload: ProfileCreate, db: Session = Depends(get_db)) -> ProfileRead:
    existing = db.execute(
        select(TeamProfile).where(TeamProfile.owner_id == payload.owner_id)
    ).scalars().all()
    if len(existing) >= MAX_PROFILES_PER_USER:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Límite de {MAX_PROFILES_PER_USER} perfiles alcanzado.",
        )

    profile = TeamProfile(owner_id=payload.owner_id, name=payload.name)
    profile.members = [
        TeamProfileMember(slot=m.slot, player_tag=m.player_tag, nickname=m.nickname)
        for m in payload.members
    ]
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _to_read(profile)


@router.patch("/{profile_id}", response_model=ProfileRead)
async def update_profile(
    profile_id: int, payload: ProfileUpdate, db: Session = Depends(get_db)
) -> ProfileRead:
    profile = db.get(TeamProfile, profile_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Perfil no encontrado.")

    if payload.name is not None:
        profile.name = payload.name
    if payload.members is not None:
        profile.members.clear()
        db.flush()
        profile.members = [
            TeamProfileMember(slot=m.slot, player_tag=m.player_tag, nickname=m.nickname)
            for m in payload.members
        ]
    db.commit()
    db.refresh(profile)
    return _to_read(profile)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(profile_id: int, db: Session = Depends(get_db)) -> None:
    profile = db.get(TeamProfile, profile_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Perfil no encontrado.")
    db.delete(profile)
    db.commit()
