"""Statistics calculator for backtest results."""

from __future__ import annotations

from typing import List

import pandas as pd


def compute_stats(
    closed_trades: list,
    final_cash: float,
    position: int,
    last_close: float,
    start_capital: float,
    equity_curve: List[float],
    start_equity: float,
) -> dict:
    """Compute aggregate statistics from backtest results.

    Args:
        closed_trades: List of ClosedTradeResult from the matcher.
        final_cash: Cash after all events.
        position: Remaining shares held.
        last_close: Last available close price (marks open position).
        start_capital: Initial capital.
        equity_curve: List of equity values after each event.
        start_equity: Equity before any events (== start_capital).

    Returns:
        Dict with keys: final_equity, total_return_pct, total_trades,
        win_rate, avg_return_pct, avg_days_held, avg_gain_per_day_pct,
        total_commission, max_drawdown_pct.
    """
    final_equity = final_cash + position * last_close
    total_return_pct = round(
        (final_equity - start_capital) / start_capital * 100, 2
    )

    total_trades = len(closed_trades)

    if total_trades == 0:
        return {
            "final_equity": round(final_equity, 2),
            "total_return_pct": total_return_pct,
            "total_trades": 0,
            "win_rate": 0.0,
            "avg_return_pct": 0.0,
            "avg_days_held": 0.0,
            "avg_gain_per_day_pct": 0.0,
            "total_commission": 0.0,
            "max_drawdown_pct": 0.0,
        }

    winning = [t for t in closed_trades if t.net_pnl > 0]
    win_rate = round(len(winning) / total_trades, 4) if total_trades else 0.0

    avg_return = round(sum(t.return_pct for t in closed_trades) / total_trades, 2)
    avg_days = round(sum(t.days_held for t in closed_trades) / total_trades, 1)
    avg_gain_per_day = round(
        sum(t.gain_per_day_pct for t in closed_trades) / total_trades, 3
    )
    total_comm = round(sum(t.commission_total for t in closed_trades), 2)

    # Drawdown from the full equity curve (prepend start equity)
    full_curve = [start_equity] + list(equity_curve)
    max_drawdown = _max_drawdown_pct(full_curve)

    return {
        "final_equity": round(final_equity, 2),
        "total_return_pct": total_return_pct,
        "total_trades": total_trades,
        "win_rate": win_rate,
        "avg_return_pct": avg_return,
        "avg_days_held": avg_days,
        "avg_gain_per_day_pct": avg_gain_per_day,
        "total_commission": total_comm,
        "max_drawdown_pct": round(max_drawdown, 2),
    }


def _max_drawdown_pct(equity: List[float]) -> float:
    """Compute maximum drawdown as a percentage from the equity curve."""
    peak = equity[0]
    max_dd = 0.0
    for val in equity:
        if val > peak:
            peak = val
        dd = (val - peak) / peak * 100
        if dd < max_dd:
            max_dd = dd
    return max_dd
