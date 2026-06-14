"""init schema

Revision ID: 0001_init_schema
Revises:
Create Date: 2026-06-04

Crea todas las tablas iniciales del proyecto. Generada a mano (no autogenerada)
porque la primera corrida se hace contra una BD vacía.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_init_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "brawlers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("rarity", sa.String(32), nullable=True),
        sa.Column("class_name", sa.String(32), nullable=True),
        sa.Column("icon_url", sa.String(512), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_brawlers_name", "brawlers", ["name"])
    op.create_index("ix_brawlers_slug", "brawlers", ["slug"])

    op.create_table(
        "maps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("game_mode", sa.String(32), nullable=False),
        sa.Column("image_url", sa.String(512), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_maps_name", "maps", ["name"])
    op.create_index("ix_maps_slug", "maps", ["slug"])
    op.create_index("ix_maps_game_mode", "maps", ["game_mode"])

    op.create_table(
        "map_stats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "map_id",
            sa.Integer(),
            sa.ForeignKey("maps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brawler_id",
            sa.Integer(),
            sa.ForeignKey("brawlers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("winrate", sa.Float(), nullable=False),
        sa.Column("pickrate", sa.Float(), nullable=False),
        sa.Column("use_rate", sa.Float(), nullable=True),
        sa.Column("sample_size", sa.Integer(), nullable=True),
        sa.Column(
            "scraped_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("map_id", "brawler_id", name="uq_map_stats_map_brawler"),
    )
    op.create_index("ix_map_stats_map_id", "map_stats", ["map_id"])
    op.create_index("ix_map_stats_brawler_id", "map_stats", ["brawler_id"])

    op.create_table(
        "synergies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "b1_id",
            sa.Integer(),
            sa.ForeignKey("brawlers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "b2_id",
            sa.Integer(),
            sa.ForeignKey("brawlers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "map_id",
            sa.Integer(),
            sa.ForeignKey("maps.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("relation_type", sa.String(16), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=True),
        sa.Column(
            "scraped_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("b1_id", "b2_id", "map_id", "relation_type", name="uq_synergy_pair"),
        sa.CheckConstraint(
            "relation_type IN ('synergy', 'counter')", name="ck_synergy_rel_type"
        ),
    )
    op.create_index("ix_synergies_b1_id", "synergies", ["b1_id"])
    op.create_index("ix_synergies_b2_id", "synergies", ["b2_id"])
    op.create_index("ix_synergies_map_id", "synergies", ["map_id"])

    op.create_table(
        "team_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("owner_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("owner_id", "name", name="uq_profile_owner_name"),
    )
    op.create_index("ix_team_profiles_owner_id", "team_profiles", ["owner_id"])

    op.create_table(
        "team_profile_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("team_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("player_tag", sa.String(16), nullable=False),
        sa.Column("nickname", sa.String(64), nullable=True),
        sa.UniqueConstraint("profile_id", "slot", name="uq_profile_member_slot"),
    )
    op.create_index("ix_team_profile_members_profile_id", "team_profile_members", ["profile_id"])
    op.create_index("ix_team_profile_members_player_tag", "team_profile_members", ["player_tag"])

    op.create_table(
        "player_proficiency",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("player_tag", sa.String(16), nullable=False),
        sa.Column(
            "brawler_id",
            sa.Integer(),
            sa.ForeignKey("brawlers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("proficiency", sa.Float(), nullable=False),
        sa.Column("trophies", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("power_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("gadgets_unlocked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("star_powers_unlocked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recent_winrate", sa.Float(), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("player_tag", "brawler_id", name="uq_proficiency_pair"),
    )
    op.create_index("ix_player_proficiency_player_tag", "player_proficiency", ["player_tag"])
    op.create_index("ix_player_proficiency_brawler_id", "player_proficiency", ["brawler_id"])


def downgrade() -> None:
    op.drop_table("player_proficiency")
    op.drop_table("team_profile_members")
    op.drop_table("team_profiles")
    op.drop_table("synergies")
    op.drop_table("map_stats")
    op.drop_table("maps")
    op.drop_table("brawlers")
