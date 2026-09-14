"""Add reversible OHLC quality metadata to daily prices."""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("daily_prices", sa.Column("is_ohlc_valid", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("daily_prices", sa.Column("validation_reason", sa.String(), nullable=True))
    op.create_index("ix_daily_prices_is_ohlc_valid", "daily_prices", ["is_ohlc_valid"])
    op.execute(sa.text("""update daily_prices set is_ohlc_valid = not (high < low or high < open or high < close or low > open or low > close), validation_reason = case when (high < low or high < open or high < close or low > open or low > close) then 'ohlc_ordering' else null end"""))

def downgrade() -> None:
    op.drop_index("ix_daily_prices_is_ohlc_valid", table_name="daily_prices")
    op.drop_column("daily_prices", "validation_reason")
    op.drop_column("daily_prices", "is_ohlc_valid")
