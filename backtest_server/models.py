"""Pydantic request/response models for the backtest server."""

from __future__ import annotations

from datetime import date as date_type
from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


# ── Bar ──────────────────────────────────────────────────────────────

class Bar(BaseModel):
    """A single OHLCV bar."""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


# ── GET response ──────────────────────────────────────────────────────

class StockDataResponse(BaseModel):
    """Response for GET /api/{area}/{ticker}."""
    ticker: str
    area: str
    start_date: str
    end_date: str
    total_bars: int
    bars: List[Bar]


class TickerListResponse(BaseModel):
    """Response for GET /api/tickers/{area}."""
    area: str
    count: int
    tickers: List[str]


class ErrorResponse(BaseModel):
    """Standard error envelope."""
    error: str
    detail: Optional[str] = None
    ticker: Optional[str] = None
    area: Optional[str] = None


# ── POST request ──────────────────────────────────────────────────────

class BacktestRequest(BaseModel):
    """Request body for POST /api/{area}/{ticker}/backtest.

    *buy_in* values are interpreted as **shares** when *buy_mode* is
    ``"shares"`` (default), or as **dollar amounts** when *buy_mode* is
    ``"dollars"``.  In dollar mode the server divides by the bar's open
    price (floored to an integer share count) and fills at that open.
    *sell_out* values are always interpreted as shares.
    """
    start_capital: float = Field(default=100000.00, ge=0.0)
    commission_per_share: float = Field(default=0.005, ge=0.0)
    buy_mode: Literal["shares", "dollars"] = Field(default="shares")
    buy_in: Dict[str, float] = Field(default_factory=dict)
    sell_out: Dict[str, int] = Field(default_factory=dict)

    @field_validator("buy_in")
    @classmethod
    def buy_in_positive(cls, v: Dict[str, float]) -> Dict[str, float]:
        for date_str, val in v.items():
            if val <= 0:
                raise ValueError(f"buy_in on {date_str} has value {val} — must be > 0")
        return v

    @field_validator("sell_out")
    @classmethod
    def sell_out_positive(cls, v: Dict[str, int]) -> Dict[str, int]:
        for date_str, qty in v.items():
            if qty <= 0:
                raise ValueError(f"sell_out on {date_str} has quantity {qty} — must be > 0")
        return v


# ── POST response ─────────────────────────────────────────────────────

class ClosedTrade(BaseModel):
    """A single matched buy→sell round-trip."""
    trade_id: int
    buy_date: str
    buy_price: float
    quantity: int
    # Additional buys (when one sell closes multiple buy lots)
    extra_buys: List[dict] = Field(default_factory=list)
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


class BacktestResponse(BaseModel):
    """Response for POST /api/{area}/{ticker}/backtest."""
    ticker: str
    area: str
    start_capital: float
    final_equity: float
    total_return_pct: float
    total_trades: int
    closed_trades: List[ClosedTrade]
    win_rate: float
    avg_return_pct: float
    avg_days_held: float
    avg_gain_per_day_pct: float
    total_commission: float
    max_drawdown_pct: float
