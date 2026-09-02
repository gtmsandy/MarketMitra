"""Add ingestion_runs table

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-03

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("instruments_upserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("snapshots_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("snapshots_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prices_accepted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prices_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prices_replaced", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prices_rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_detail", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("ingestion_runs")
