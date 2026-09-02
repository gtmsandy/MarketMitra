"""Initial schema: instruments, market_snapshots, daily_prices

Revision ID: 0001
Revises:
Create Date: 2026-09-03

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("company_name", sa.String(), nullable=False),
        sa.Column("sector", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("symbol"),
    )

    op.create_table(
        "market_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nepse_index", sa.Float(), nullable=False),
        sa.Column("index_change", sa.Float(), nullable=False),
        sa.Column("index_change_percent", sa.Float(), nullable=False),
        sa.Column("turnover", sa.Float(), nullable=False),
        sa.Column("total_volume", sa.Integer(), nullable=False),
        sa.Column("total_transactions", sa.Integer(), nullable=False),
        sa.Column("market_status", sa.String(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_snapshots_captured_at", "market_snapshots", ["captured_at"])

    op.create_table(
        "daily_prices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("date", sa.String(), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.Column("turnover", sa.Float(), nullable=False),
        sa.Column("change", sa.Float(), nullable=False),
        sa.Column("change_percent", sa.Float(), nullable=False),
        sa.Column("previous_close", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["symbol"], ["instruments.symbol"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "date", name="uq_daily_price_symbol_date"),
    )


def downgrade() -> None:
    op.drop_table("daily_prices")
    op.drop_index("ix_market_snapshots_captured_at", table_name="market_snapshots")
    op.drop_table("market_snapshots")
    op.drop_table("instruments")
