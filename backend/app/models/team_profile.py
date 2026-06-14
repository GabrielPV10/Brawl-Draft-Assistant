from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

MAX_PROFILES_PER_USER = 5


class TeamProfile(Base):
    """Perfil guardado de un equipo (hasta MAX_PROFILES_PER_USER por usuario).

    En la v1 el "owner" es el device_id del Android (ya que no hay auth).
    """

    __tablename__ = "team_profiles"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_profile_owner_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(String(128), index=True)  # device_id u otro identificador
    name: Mapped[str] = mapped_column(String(64))  # "Squad Ranked", "Squad casual"...
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    members: Mapped[list["TeamProfileMember"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="TeamProfileMember.slot",
    )


class TeamProfileMember(Base):
    """Un slot del perfil (slot 0 = tú, 1 y 2 = cuates)."""

    __tablename__ = "team_profile_members"
    __table_args__ = (UniqueConstraint("profile_id", "slot", name="uq_profile_member_slot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("team_profiles.id", ondelete="CASCADE"), index=True
    )
    slot: Mapped[int] = mapped_column(Integer)  # 0, 1, 2
    player_tag: Mapped[str] = mapped_column(String(16), index=True)  # #ABC123XY (sin #)
    nickname: Mapped[str | None] = mapped_column(String(64), nullable=True)

    profile: Mapped[TeamProfile] = relationship(back_populates="members")
