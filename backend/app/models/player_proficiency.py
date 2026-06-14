from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class PlayerProficiency(Base):
    """Score de dominio (0-100) de un jugador con un brawler.

    Calculado desde la API oficial de Supercell:
        0.30 · normalizar(trofeos)
      + 0.20 · (nivel_poder / 11)
      + 0.15 · gadgets_desbloqueados
      + 0.15 · star_powers_desbloqueados
      + 0.20 · winrate_reciente (battlelog últimas 25)
    """

    __tablename__ = "player_proficiency"
    __table_args__ = (UniqueConstraint("player_tag", "brawler_id", name="uq_proficiency_pair"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_tag: Mapped[str] = mapped_column(String(16), index=True)
    brawler_id: Mapped[int] = mapped_column(
        ForeignKey("brawlers.id", ondelete="CASCADE"), index=True
    )

    proficiency: Mapped[float] = mapped_column(Float)  # 0.0 - 100.0
    trophies: Mapped[int] = mapped_column(Integer, default=0)
    power_level: Mapped[int] = mapped_column(Integer, default=1)
    gadgets_unlocked: Mapped[int] = mapped_column(Integer, default=0)
    star_powers_unlocked: Mapped[int] = mapped_column(Integer, default=0)
    recent_winrate: Mapped[float | None] = mapped_column(Float, nullable=True)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
