"""drop unique constraints on maps.name and maps.slug

Revision ID: 0002_drop_map_name_slug_unique
Revises: 0001_init_schema
Create Date: 2026-06-14

BrawlAPI devuelve el mismo nombre de mapa en distintos modos de juego con IDs
diferentes. El único identificador real es `id` (PK). Los constraints UNIQUE en
name y slug provocan UniqueViolation al hacer el seed con datos reales.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_drop_map_name_slug_unique"
down_revision: str | None = "0001_init_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("maps_name_key", "maps", type_="unique")
    op.drop_constraint("maps_slug_key", "maps", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint("maps_name_key", "maps", ["name"])
    op.create_unique_constraint("maps_slug_key", "maps", ["slug"])
