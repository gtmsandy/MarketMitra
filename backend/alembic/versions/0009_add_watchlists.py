"""Add private user-owned watchlists."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "watchlists",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint("name = lower(trim(name))", name="ck_watchlists_name_normalized"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "name", name="uq_watchlists_owner_name"),
    )
    op.create_index("ix_watchlists_owner_id", "watchlists", ["owner_id"])

    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("watchlist_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(["symbol"], ["instruments.symbol"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["watchlist_id"], ["watchlists.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("watchlist_id", "symbol", name="uq_watchlist_items_watchlist_symbol"),
    )
    op.create_index("ix_watchlist_items_watchlist_id", "watchlist_items", ["watchlist_id"])
    op.create_index(
        "ix_watchlist_items_watchlist_created",
        "watchlist_items",
        ["watchlist_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_watchlist_items_watchlist_created", table_name="watchlist_items")
    op.drop_index("ix_watchlist_items_watchlist_id", table_name="watchlist_items")
    op.drop_table("watchlist_items")
    op.drop_index("ix_watchlists_owner_id", table_name="watchlists")
    op.drop_table("watchlists")
