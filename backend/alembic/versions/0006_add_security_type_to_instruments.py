"""Add security_type to instruments to separate asset class from economic sector

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-11
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add security_type column with default 'EQUITY'
    op.add_column(
        "instruments",
        sa.Column("security_type", sa.String(), nullable=False, server_default="EQUITY"),
    )

    # 2. Populate deterministic classification based on audited source categories
    op.execute("UPDATE instruments SET security_type = 'PROMOTER_SHARE' WHERE sector = 'Promoter Share'")
    op.execute("UPDATE instruments SET security_type = 'DEBENTURE' WHERE sector = 'Corporate Debentures'")
    op.execute("UPDATE instruments SET security_type = 'MUTUAL_FUND' WHERE sector = 'Mutual Fund'")
    op.execute("UPDATE instruments SET security_type = 'GOVERNMENT_BOND' WHERE sector = 'Government Bonds'")
    op.execute("UPDATE instruments SET security_type = 'PREFERENCE_SHARE' WHERE sector = 'Preference Share'")
    op.execute("UPDATE instruments SET security_type = 'EQUITY' WHERE security_type IS NULL OR security_type = 'EQUITY'")

    # 3. Create index on security_type
    op.create_index("ix_instruments_security_type", "instruments", ["security_type"])


def downgrade() -> None:
    op.drop_index("ix_instruments_security_type", table_name="instruments")
    op.drop_column("instruments", "security_type")
