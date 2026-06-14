from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class MapStats(Base):
    """Winrate y pickrate de cada brawler en cada mapa (scrapeado de Brawlify)."""

    __tablename__ = "map_stats"
    __table_args__ = (UniqueConstraint("map_id", "brawler_id", name="uq_map_stats_map_brawler"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    map_id: Mapped[int] = mapped_column(ForeignKey("maps.id", ondelete="CASCADE"), index=True)
    brawler_id: Mapped[int] = mapped_column(
        ForeignKey("brawlers.id", ondelete="CASCADE"), index=True
    )

    winrate: Mapped[float] = mapped_column(Float)  # 0.0 - 1.0
    pickrate: Mapped[float] = mapped_column(Float)  # 0.0 - 1.0
    use_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
