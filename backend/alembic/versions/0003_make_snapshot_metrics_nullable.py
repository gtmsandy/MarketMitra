"""Make market snapshot turnover, volume, and transactions nullable

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-05

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("market_snapshots", "turnover", existing_type=sa.Float(), nullable=True)
    op.alter_column("market_snapshots", "total_volume", existing_type=sa.Integer(), nullable=True)
    op.alter_column("market_snapshots", "total_transactions", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE market_snapshots SET turnover = 0.0 WHERE turnover IS NULL")
    op.execute("UPDATE market_snapshots SET total_volume = 0 WHERE total_volume IS NULL")
    op.execute("UPDATE market_snapshots SET total_transactions = 0 WHERE total_transactions IS NULL")
    op.alter_column("market_snapshots", "turnover", existing_type=sa.Float(), nullable=False)
    op.alter_column("market_snapshots", "total_volume", existing_type=sa.Integer(), nullable=False)
    op.alter_column("market_snapshots", "total_transactions", existing_type=sa.Integer(), nullable=False)
