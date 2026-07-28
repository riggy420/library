"""FastAPI backtest server entry point.

Two endpoints:
    GET  /api/{area}/{ticker}          — fetch historical OHLCV bars
    POST /api/{area}/{ticker}/backtest — run a batch backtest
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, HTTPException, Path as PathParam, Query
from fastapi.responses import JSONResponse

from .config import DATA_DIR, DEFAULT_CAPITAL, DEFAULT_COMMISSION, DEFAULT_YEARS
from .loader import DataNotFoundError, NoDataInRangeError, load_bars
from .matcher import run_backtest
from .models import (
    BacktestRequest,
    BacktestResponse,
    Bar,
    ClosedTrade,
    ErrorResponse,
    StockDataResponse,
    TickerListResponse,
)
from .stats import compute_stats

# ── App ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Backtest Server",
    version="1.0.0",
    description="Serve historical stock data and run batch backtests.",
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── Exception handlers ─────────────────────────────────────────────────

@app.exception_handler(DataNotFoundError)
async def data_not_found_handler(request, exc: DataNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"error": "Ticker not found", "detail": str(exc)},
    )


@app.exception_handler(NoDataInRangeError)
async def no_data_in_range_handler(request, exc: NoDataInRangeError):
    return JSONResponse(
        status_code=404,
        content={"error": "No data in range", "detail": str(exc)},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"error": str(exc)},
    )


# ── Helpers ────────────────────────────────────────────────────────────

def _bars_to_dicts(df) -> list[dict]:
    """Convert a pandas DataFrame to a list of Bar-compatible dicts."""
    bars = []
    for idx, row in df.iterrows():
        bars.append({
            "date": idx.strftime("%Y-%m-%d"),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]),
        })
    return bars


# ── Routes ─────────────────────────────────────────────────────────────

@app.get(
    "/api/tickers/{area}",
    response_model=TickerListResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Unknown area"},
    },
)
async def list_tickers(
    area: str = PathParam(..., description="Market area: America, SS, SZ"),
):
    """List all available tickers for a market area.

    Scans the *stock_data/{area}/* directory for ``.txt`` files and returns
    every ticker symbol (filename stem).
    """
    valid_areas = _list_areas()
    if area not in valid_areas:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown area '{area}'. Available: {', '.join(valid_areas)}",
        )

    data_path = Path(DATA_DIR) / area
    tickers = sorted(
        f.stem for f in data_path.glob("*.txt") if f.is_file()
    )

    return TickerListResponse(
        area=area,
        count=len(tickers),
        tickers=tickers,
    )


@app.get(
    "/api/{area}/{ticker}",
    response_model=StockDataResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Ticker or data not found"},
    },
)
async def get_stock_data(
    area: str = PathParam(..., description="Market area: America, SS, SZ"),
    ticker: str = PathParam(..., description="Stock ticker symbol, e.g. AAPL"),
    start_range: Optional[str] = Query(
        default=None,
        description="Start date (YYYY-MM-DD). Defaults to 5 years ago.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    ),
    end_range: Optional[str] = Query(
        default=None,
        description="End date (YYYY-MM-DD). Defaults to today.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    ),
):
    """Fetch historical OHLCV bars for a stock.

    Returns up to 5 years of daily data by default.  Use *start_range*
    and *end_range* to narrow the window.
    """
    # Validate area
    valid_areas = _list_areas()
    if area not in valid_areas:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown area '{area}'. Available: {', '.join(valid_areas)}",
        )

    df = load_bars(ticker, area, start_range, end_range)

    bars = _bars_to_dicts(df)

    return StockDataResponse(
        ticker=ticker.upper(),
        area=area,
        start_date=df.index[0].strftime("%Y-%m-%d"),
        end_date=df.index[-1].strftime("%Y-%m-%d"),
        total_bars=len(bars),
        bars=bars,
    )


@app.post(
    "/api/{area}/{ticker}/backtest",
    response_model=BacktestResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request (bad dates, insufficient shares, etc.)"},
        404: {"model": ErrorResponse, "description": "Ticker not found"},
    },
)
async def post_backtest(
    area: str = PathParam(..., description="Market area: America, SS, SZ"),
    ticker: str = PathParam(..., description="Stock ticker symbol, e.g. AAPL"),
    body: BacktestRequest = None,
):
    """Run a batch backtest.

    Submit buy_in and sell_out date→quantity maps.  The server resolves
    dates to the nearest trading day, executes FIFO-matched round-trips,
    and returns performance statistics including win rate, average gain
    per day, and max drawdown.
    """
    # Validate area
    valid_areas = _list_areas()
    if area not in valid_areas:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown area '{area}'. Available: {', '.join(valid_areas)}",
        )

    # Both maps cannot be empty
    if not body.buy_in and not body.sell_out:
        raise HTTPException(
            status_code=400,
            detail="buy_in and sell_out cannot both be empty",
        )

    # Load ALL available data for this ticker (needed to resolve any date)
    df = load_bars(ticker, area)

    start_capital = body.start_capital or DEFAULT_CAPITAL
    commission = body.commission_per_share or DEFAULT_COMMISSION

    # Run the backtest
    try:
        closed_trades, final_cash, equity_curve, position = run_backtest(
            df, body.buy_in, body.sell_out, start_capital, commission,
            buy_mode=body.buy_mode,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    last_date = df.index[-1]
    last_close = float(df.loc[last_date, "Close"])

    # Compute stats
    stats = compute_stats(
        closed_trades=closed_trades,
        final_cash=final_cash,
        position=position,
        last_close=last_close,
        start_capital=start_capital,
        equity_curve=equity_curve,
        start_equity=start_capital,
    )

    # Build response closed trades
    response_trades = []
    for i, ct in enumerate(closed_trades, 1):
        trade_dict = {
            "trade_id": i,
            "buy_date": ct.buy_date,
            "buy_price": ct.buy_price,
            "quantity": ct.quantity,
            "extra_buys": ct.extra_buys,
            "total_quantity": ct.total_quantity,
            "avg_entry_price": ct.avg_entry_price,
            "sell_date": ct.sell_date,
            "sell_price": ct.sell_price,
            "gross_pnl": ct.gross_pnl,
            "commission_total": ct.commission_total,
            "net_pnl": ct.net_pnl,
            "return_pct": ct.return_pct,
            "days_held": ct.days_held,
            "gain_per_day_pct": ct.gain_per_day_pct,
        }
        response_trades.append(trade_dict)

    return BacktestResponse(
        ticker=ticker.upper(),
        area=area,
        start_capital=start_capital,
        final_equity=stats["final_equity"],
        total_return_pct=stats["total_return_pct"],
        total_trades=stats["total_trades"],
        closed_trades=response_trades,
        win_rate=stats["win_rate"],
        avg_return_pct=stats["avg_return_pct"],
        avg_days_held=stats["avg_days_held"],
        avg_gain_per_day_pct=stats["avg_gain_per_day_pct"],
        total_commission=stats["total_commission"],
        max_drawdown_pct=stats["max_drawdown_pct"],
    )


# ── Utility ────────────────────────────────────────────────────────────

def _list_areas() -> list[str]:
    """Discover available market areas from the data directory."""
    data_path = Path(DATA_DIR)
    if not data_path.exists():
        return []
    return sorted([
        d.name for d in data_path.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ])


# ── Watchlist ─────────────────────────────────────────────────────────

_WATCHLIST_PATH = Path(__file__).resolve().parent.parent / "alert_watchlist.txt"


@app.get("/api/watchlist")
async def get_watchlist():
    """Return the current watchlist entries (non-comment lines)."""
    if not _WATCHLIST_PATH.exists():
        return {"entries": [], "path": str(_WATCHLIST_PATH)}
    entries: list[dict] = []
    for line in _WATCHLIST_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) >= 2:
            entries.append({
                "ticker": parts[0].upper(),
                "threshold": float(parts[1]),
                "field": parts[2] if len(parts) >= 3 else "last",
            })
    return {"entries": entries, "path": str(_WATCHLIST_PATH)}


@app.post("/api/watchlist")
async def post_watchlist(
    tickers: list[dict] = Body(
        ...,
        examples=[{"ticker": "AAPL", "threshold": 200.0, "field": "last"}],
    ),
):
    """Add entries to the alert watchlist.

    Each entry must have ``ticker`` and ``threshold``; ``field`` is optional
    (default ``"last"``).  Duplicates are skipped.
    """
    added = []
    for entry in tickers:
        ticker = entry["ticker"].upper()
        threshold = float(entry["threshold"])
        field = entry.get("field", "last")
        try:
            # Use the WatchlistMonitor helper if importable, otherwise raw write
            from ib_paper.watchlist import WatchlistMonitor
            before = _read_watchlist_tickers()
            WatchlistMonitor.append(str(_WATCHLIST_PATH), ticker, threshold, field)
            after = _read_watchlist_tickers()
            if ticker in after and ticker not in before:
                added.append(ticker)
        except ImportError:
            # Fallback — write directly
            before = _read_watchlist_tickers()
            if ticker not in before:
                line = f"{ticker} {threshold} {field}".strip()
                with _WATCHLIST_PATH.open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
                added.append(ticker)

    return {"added": added, "total": len(_read_watchlist_tickers()),
            "path": str(_WATCHLIST_PATH)}


@app.delete("/api/watchlist/{ticker}")
async def delete_watchlist_entry(
    ticker: str = PathParam(..., description="Ticker to remove from the watchlist"),
):
    """Remove all entries for *ticker* from the watchlist."""
    try:
        from ib_paper.watchlist import WatchlistMonitor
        removed = WatchlistMonitor.remove(str(_WATCHLIST_PATH), ticker)
    except ImportError:
        removed = _remove_from_watchlist(ticker)
    return {"ticker": ticker.upper(), "removed": removed}


def _read_watchlist_tickers() -> set:
    if not _WATCHLIST_PATH.exists():
        return set()
    tickers = set()
    for line in _WATCHLIST_PATH.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            parts = s.split()
            if parts:
                tickers.add(parts[0].upper())
    return tickers


def _remove_from_watchlist(ticker: str) -> bool:
    if not _WATCHLIST_PATH.exists():
        return False
    lines = _WATCHLIST_PATH.read_text(encoding="utf-8").splitlines()
    new_lines = []
    removed = False
    tu = ticker.upper()
    for line in lines:
        s = line.strip()
        if s == "" or s.startswith("#"):
            new_lines.append(line)
            continue
        parts = s.split()
        if parts and parts[0].upper() == tu:
            removed = True
            continue
        new_lines.append(line)
    if removed:
        _WATCHLIST_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return removed


# ── Health check ───────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "available_areas": _list_areas()}


# ── Entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    from .config import HOST, PORT

    print(f"Data directory: {DATA_DIR}")
    print(f"Available areas: {_list_areas()}")
    uvicorn.run(app, host=HOST, port=PORT)
