"""Add owner-scoped immutable portfolio ledgers."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False, server_default="NPR"),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("base_currency = 'NPR'", name="ck_portfolios_base_currency"),
        sa.CheckConstraint("name = trim(name) and length(name) > 0", name="ck_portfolios_name"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_portfolios_owner_id", "portfolios", ["owner_id"])
    op.create_index("ix_portfolios_owner_active", "portfolios", ["owner_id", "archived_at"])
    op.create_index(
        "uq_portfolios_owner_name_ci", "portfolios", ["owner_id", sa.text("lower(name)")],
        unique=True, postgresql_where=sa.text("archived_at is null"),
    )

    op.create_table(
        "portfolio_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("side", sa.String(length=4), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("trade_sequence", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("unit_price", sa.Numeric(24, 8), nullable=False),
        sa.Column("fees", sa.Numeric(24, 8), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("side in ('BUY', 'SELL')", name="ck_portfolio_transactions_side"),
        sa.CheckConstraint("trade_sequence >= 0", name="ck_portfolio_transactions_sequence"),
        sa.CheckConstraint("quantity > 0", name="ck_portfolio_transactions_quantity"),
        sa.CheckConstraint("unit_price > 0", name="ck_portfolio_transactions_unit_price"),
        sa.CheckConstraint("fees >= 0", name="ck_portfolio_transactions_fees"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["symbol"], ["instruments.symbol"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("portfolio_id", "idempotency_key", name="uq_portfolio_transactions_idempotency"),
        sa.UniqueConstraint("portfolio_id", "trade_date", "trade_sequence", name="uq_portfolio_transactions_order"),
    )
    op.create_index("ix_portfolio_transactions_portfolio_id", "portfolio_transactions", ["portfolio_id"])
    op.create_index(
        "ix_portfolio_transactions_portfolio_order", "portfolio_transactions",
        ["portfolio_id", "trade_date", "trade_sequence"],
    )


def downgrade() -> None:
    op.drop_index("ix_portfolio_transactions_portfolio_order", table_name="portfolio_transactions")
    op.drop_index("ix_portfolio_transactions_portfolio_id", table_name="portfolio_transactions")
    op.drop_table("portfolio_transactions")
    op.drop_index("uq_portfolios_owner_name_ci", table_name="portfolios")
    op.drop_index("ix_portfolios_owner_active", table_name="portfolios")
    op.drop_index("ix_portfolios_owner_id", table_name="portfolios")
    op.drop_table("portfolios")
