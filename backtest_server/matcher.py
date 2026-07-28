"""FIFO buy/sell matching engine.

Takes raw buy-in and sell-out dictionaries, resolves dates against
historical bars, and produces a list of ClosedTrade results.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Dict, List

import pandas as pd

from .loader import resolve_date


@dataclass
class BuyLot:
    """A single buy lot sitting in the inventory queue."""
    buy_date: str
    buy_price: float
    remaining_qty: int
    original_qty: int


@dataclass
class ClosedTradeResult:
    """Internal result before building the final response."""
    buy_date: str
    buy_price: float
    quantity: int
    extra_buys: List[dict]
    total_quantity: int
    avg_entry_price: float
    sell_date: str
    sell_price: float
    gross_pnl: float
    commission_total: float
    net_pnl: float
    return_pct: float
    days_held: int
    gain_per_day_pct: float


def _get_prices(df: pd.DataFrame, date_str: str) -> tuple[str, float, float]:
    """Resolve *date_str* to a trading day and return (date, open, close)."""
    resolved = resolve_date(df, date_str)
    open_price = float(df.loc[resolved, "Open"])
    close_price = float(df.loc[resolved, "Close"])
    return resolved.strftime("%Y-%m-%d"), open_price, close_price


def run_backtest(
    df: pd.DataFrame,
    buy_in: Dict[str, float],
    sell_out: Dict[str, int],
    start_capital: float,
    commission_per_share: float,
    buy_mode: str = "shares",
) -> tuple[List[ClosedTradeResult], float, List[float]]:
    """Execute a FIFO-matched backtest.

    Args:
        df: DataFrame of bars with Date index and OHLCV columns.
        buy_in: Map of date → shares (buy_mode="shares") or dollars (buy_mode="dollars").
        sell_out: Map of date → shares.
        start_capital: Initial cash balance.
        commission_per_share: Per-share commission.
        buy_mode: ``"shares"`` (default) — *buy_in* values are share counts;
                  ``"dollars"`` — *buy_in* values are dollar amounts, converted
                  to integer shares via ``floor(dollars / open_price)``.

    Returns:
        (closed_trades, final_cash, equity_curve, final_position)

    Raises:
        ValueError: On insufficient shares for a sell, or dates with no data.
    """
    # Build chronological event list
    events: list[tuple[str, str, float]] = []  # (date, type, qty_or_dollars)
    for date_str, val in buy_in.items():
        events.append((date_str, "buy", val))
    for date_str, qty in sell_out.items():
        events.append((date_str, "sell", float(qty)))

    # Sort by date
    events.sort(key=lambda e: e[0])

    inventory: deque[BuyLot] = deque()
    closed_trades: list[ClosedTradeResult] = []
    trade_counter = 0
    equity_curve: list[float] = []
    cash = start_capital
    position = 0

    for date_str, event_type, val in events:
        resolved_date, open_price, close_price = _get_prices(df, date_str)

        if event_type == "buy":
            if buy_mode == "dollars":
                # val = dollar amount → convert to shares at open price
                if open_price <= 0:
                    raise ValueError(
                        f"Open price is {open_price} on {resolved_date} — "
                        f"cannot convert dollars to shares"
                    )
                shares = int(val / open_price)
                fill_price = open_price
            else:
                shares = int(val)
                fill_price = close_price

            if shares <= 0:
                # dollar amount too small for even 1 share — skip
                equity_curve.append(cash + position * close_price)
                continue

            cost = shares * fill_price + shares * commission_per_share
            if cost > cash:
                raise ValueError(
                    f"Insufficient cash on {resolved_date}: "
                    f"need ${cost:,.2f} for {shares} shares @ ${fill_price:.2f} "
                    f"but only ${cash:,.2f} available"
                )
            cash -= cost
            position += shares
            inventory.append(BuyLot(
                buy_date=resolved_date,
                buy_price=fill_price,
                remaining_qty=shares,
                original_qty=shares,
            ))

        else:  # sell
            sell_qty = int(val)
            if sell_qty > position:
                raise ValueError(
                    f"Insufficient shares: sell on {resolved_date} "
                    f"for {sell_qty} shares but only {position} held"
                )

            proceeds = sell_qty * close_price - sell_qty * commission_per_share
            cash += proceeds
            position -= sell_qty

            remaining_to_sell = sell_qty
            lots_used: list[dict] = []

            while remaining_to_sell > 0 and inventory:
                lot = inventory[0]
                take = min(lot.remaining_qty, remaining_to_sell)
                lots_used.append({
                    "buy_date": lot.buy_date,
                    "buy_price": lot.buy_price,
                    "quantity": take,
                })
                lot.remaining_qty -= take
                remaining_to_sell -= take
                if lot.remaining_qty == 0:
                    inventory.popleft()

            # Build a ClosedTrade for this sell event's matched lots
            trade_counter += 1
            total_qty = sum(lt["quantity"] for lt in lots_used)
            avg_entry = (
                sum(lt["buy_price"] * lt["quantity"] for lt in lots_used) / total_qty
            )

            entry_value = avg_entry * total_qty
            exit_value = close_price * total_qty
            gross_pnl = exit_value - entry_value
            comm = total_qty * commission_per_share * 2  # buy + sell commission
            net_pnl = gross_pnl - comm
            return_pct = (net_pnl / entry_value) * 100 if entry_value != 0 else 0.0

            first_lot = lots_used[0]
            days_held = (
                pd.Timestamp(resolved_date) - pd.Timestamp(first_lot["buy_date"])
            ).days
            gain_per_day = (net_pnl / (entry_value * days_held)) * 100 if days_held > 0 else 0.0

            extra_buys = []
            if len(lots_used) > 1:
                for lt in lots_used[1:]:
                    extra_buys.append({
                        "buy_date": lt["buy_date"],
                        "buy_price": lt["buy_price"],
                        "quantity": lt["quantity"],
                    })

            closed_trades.append(ClosedTradeResult(
                buy_date=first_lot["buy_date"],
                buy_price=first_lot["buy_price"],
                quantity=first_lot["quantity"],
                extra_buys=extra_buys,
                total_quantity=total_qty,
                avg_entry_price=round(avg_entry, 2),
                sell_date=resolved_date,
                sell_price=round(close_price, 2),
                gross_pnl=round(gross_pnl, 2),
                commission_total=round(comm, 2),
                net_pnl=round(net_pnl, 2),
                return_pct=round(return_pct, 2),
                days_held=days_held,
                gain_per_day_pct=round(gain_per_day, 3),
            ))

        # Record equity after each event
        last_close = close_price
        equity_curve.append(cash + position * last_close)

    return closed_trades, cash, equity_curve, position
