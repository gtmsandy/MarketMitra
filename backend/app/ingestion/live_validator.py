"""Live regulatory validation rules for NEPSE equity trading and benchmark index.

Enforces:
1. Normal session individual equity daily fluctuation limit (±15%).
2. Pre-open session order price limit (±5%).
3. Market-wide index circuit breakers (5% in first 2 hours -> 15 min halt, 8% -> day halt).

Strictly preserves source truth: never clamps, mutates, or rewrites values.
"""

from dataclasses import dataclass
from enum import Enum


class IndexCircuitStatus(str, Enum):
    """Market-wide benchmark index circuit breaker status."""
    NORMAL = "NORMAL"
    LEVEL_1_HALT_15M = "LEVEL_1_HALT_15M"  # 5% index movement within first 2 hours
    LEVEL_2_HALT_DAY = "LEVEL_2_HALT_DAY"  # 8% index movement at any time


@dataclass
class LiveStockValidationResult:
    """Result of validating a real-time stock quote against NEPSE session rules."""
    is_valid: bool
    symbol: str
    ltp: float
    previous_close: float
    calculated_change_percent: float
    rule_name: str
    message: str
    action: str  # "ACCEPT", "REJECT", "FLAG_CORPORATE_ACTION"


def validate_live_stock_quote(
    symbol: str,
    ltp: float,
    previous_close: float,
    is_pre_open: bool = False,
    is_corporate_action_day: bool = False,
) -> LiveStockValidationResult:
    """Validate an individual equity quote against current NEPSE trading limits.

    Never clamps values with min/max. Evaluates exact percentage deviation:
    - Normal session: -15% <= change <= +15%
    - Pre-open session: -5% <= change <= +5%
    - Confirmed corporate actions (bonus/rights/split adjustments): flagged for audit.
    """
    if previous_close <= 0:
        return LiveStockValidationResult(
            is_valid=False,
            symbol=symbol,
            ltp=ltp,
            previous_close=previous_close,
            calculated_change_percent=0.0,
            rule_name="previous_close_positive",
            message=f"Invalid previous_close ({previous_close}) for {symbol}",
            action="REJECT",
        )

    if ltp <= 0:
        return LiveStockValidationResult(
            is_valid=False,
            symbol=symbol,
            ltp=ltp,
            previous_close=previous_close,
            calculated_change_percent=0.0,
            rule_name="ltp_positive",
            message=f"Invalid ltp ({ltp}) for {symbol}",
            action="REJECT",
        )

    pct_change = round(((ltp - previous_close) / previous_close) * 100, 4)

    if is_pre_open:
        limit = 5.0
        if -limit <= pct_change <= limit:
            return LiveStockValidationResult(
                is_valid=True,
                symbol=symbol,
                ltp=ltp,
                previous_close=previous_close,
                calculated_change_percent=pct_change,
                rule_name="pre_open_limit_5_percent",
                message=f"Within ±5% pre-open limit ({pct_change:+0.2f}%)",
                action="ACCEPT",
            )
        return LiveStockValidationResult(
            is_valid=False,
            symbol=symbol,
            ltp=ltp,
            previous_close=previous_close,
            calculated_change_percent=pct_change,
            rule_name="pre_open_limit_5_percent",
            message=f"Exceeds ±5% pre-open limit ({pct_change:+0.2f}%)",
            action="REJECT",
        )

    # Normal regular trading session (±15% limit)
    normal_limit = 15.0
    if -normal_limit <= pct_change <= normal_limit:
        return LiveStockValidationResult(
            is_valid=True,
            symbol=symbol,
            ltp=ltp,
            previous_close=previous_close,
            calculated_change_percent=pct_change,
            rule_name="stock_daily_limit_15_percent",
            message=f"Within ±15% daily limit ({pct_change:+0.2f}%)",
            action="ACCEPT",
        )

    # If outside ±15%, check if this security underwent a corporate action adjustment
    if is_corporate_action_day:
        return LiveStockValidationResult(
            is_valid=True,
            symbol=symbol,
            ltp=ltp,
            previous_close=previous_close,
            calculated_change_percent=pct_change,
            rule_name="corporate_action_opening_band",
            message=f"Exceeds normal ±15% but accepted due to corporate action adjustment ({pct_change:+0.2f}%)",
            action="FLAG_CORPORATE_ACTION",
        )

    return LiveStockValidationResult(
        is_valid=False,
        symbol=symbol,
        ltp=ltp,
        previous_close=previous_close,
        calculated_change_percent=pct_change,
        rule_name="stock_daily_limit_15_percent",
        message=f"Exceeds ±15% normal trading circuit limit ({pct_change:+0.2f}%)",
        action="REJECT",
    )


def validate_index_circuit_breaker(
    index_change_percent: float,
    session_minutes: int,
) -> tuple[IndexCircuitStatus, str]:
    """Evaluate market-wide circuit breaker state for NEPSE index.

    Current 2-tier rules (implemented since April 2026):
    - Level 1: 5% movement (up or down) in first 2 hours (<=120 min) -> 15 min market halt.
    - Level 2: 8% movement (up or down) at any time -> trading halted for remainder of day.

    This rule is strictly independent of individual stock price fluctuation limits.
    """
    abs_move = abs(index_change_percent)

    if abs_move >= 8.0:
        return (
            IndexCircuitStatus.LEVEL_2_HALT_DAY,
            f"Index moved {index_change_percent:+0.2f}% (>= 8.0%): Market halted for remainder of day",
        )

    if session_minutes <= 120 and abs_move >= 5.0:
        return (
            IndexCircuitStatus.LEVEL_1_HALT_15M,
            f"Index moved {index_change_percent:+0.2f}% (>= 5.0%) in first 2 hours: 15-minute trading halt",
        )

    return IndexCircuitStatus.NORMAL, "Normal index trading"
