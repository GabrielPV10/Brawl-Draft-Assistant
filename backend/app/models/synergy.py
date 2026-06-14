from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Synergy(Base):
    """Matriz de sinergia y counters entre brawlers (derivada de team comps de Brawlify).

    relation_type:
        - 'synergy': qué tan bien juegan juntos (mismo equipo)
        - 'counter': qué tan bien b1 le gana a b2 (equipos opuestos)
    """

    __tablename__ = "synergies"
    __table_args__ = (
        UniqueConstraint("b1_id", "b2_id", "map_id", "relation_type", name="uq_synergy_pair"),
        CheckConstraint("relation_type IN ('synergy', 'counter')", name="ck_synergy_rel_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    b1_id: Mapped[int] = mapped_column(ForeignKey("brawlers.id", ondelete="CASCADE"), index=True)
    b2_id: Mapped[int] = mapped_column(ForeignKey("brawlers.id", ondelete="CASCADE"), index=True)
    map_id: Mapped[int | None] = mapped_column(
        ForeignKey("maps.id", ondelete="CASCADE"), nullable=True, index=True
    )
    relation_type: Mapped[str] = mapped_column(String(16))
    score: Mapped[float] = mapped_column(Float)  # -1.0 a 1.0
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
