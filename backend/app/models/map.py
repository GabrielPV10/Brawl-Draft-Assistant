from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Map(Base):
    """Catálogo de mapas competitivos."""

    __tablename__ = "maps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    slug: Mapped[str] = mapped_column(String(128), index=True)
    game_mode: Mapped[str] = mapped_column(String(32), index=True)  # Knockout, Brawl Ball, ...
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Map id={self.id} name={self.name!r} mode={self.game_mode}>"
