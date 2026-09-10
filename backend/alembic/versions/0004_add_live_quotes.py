"""Add live_quotes table for intraday and real-time market data

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-10
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "live_quotes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(), sa.ForeignKey("instruments.symbol", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("turnover", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("provider", sa.String(), nullable=False, server_default="unspecified"),
        sa.Column("source_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_live_quotes_symbol", "live_quotes", ["symbol"])
    op.create_index("ix_live_quotes_timestamp", "live_quotes", ["timestamp"])
    op.create_index("ix_live_quotes_symbol_timestamp", "live_quotes", ["symbol", "timestamp"])


def downgrade() -> None:
    op.drop_index("ix_live_quotes_symbol_timestamp", table_name="live_quotes")
    op.drop_index("ix_live_quotes_timestamp", table_name="live_quotes")
    op.drop_index("ix_live_quotes_symbol", table_name="live_quotes")
    op.drop_table("live_quotes")
