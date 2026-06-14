from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Brawler(Base):
    """Catálogo de brawlers (sembrado desde BrawlAPI)."""

    __tablename__ = "brawlers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # ID oficial Supercell
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    rarity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    class_name: Mapped[str | None] = mapped_column(String(32), nullable=True)  # Damage Dealer, etc.
    icon_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Brawler id={self.id} name={self.name!r}>"
