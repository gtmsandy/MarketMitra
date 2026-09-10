"""Add unique constraint on live_quotes(symbol, timestamp) for database-level idempotency

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-10
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_live_quotes_symbol_timestamp",
        "live_quotes",
        ["symbol", "timestamp"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_live_quotes_symbol_timestamp",
        "live_quotes",
        type_="unique",
    )
