"""
random_algorithm.py -- Drop-rebound strategy backtest across all tickers.

Strategy:
    For every ticker in America, scan 5 years of daily bars for days where
    the close-to-close drop exceeds 5 %.  On each signal:
        - BUY  $1,000 worth at the **next** trading day's open  (dollars mode)
        - SELL all accumulated shares at the close **5 trading days**
          after the drop day

All buy/sell pairs for a ticker are bundled into a single POST to
``/api/{area}/{ticker}/backtest``, which executes them chronologically
(FIFO) and returns per-trade P&L plus aggregate statistics.

Output:
    - ``results.json``  -- full per-ticker backtest data
    - ``results.csv``   -- flat summary table (one row per ticker)
    - Console report    -- top-10 by gain/day, top-10 by win rate,
                          aggregate P&L across all tickers, distribution
"""

from __future__ import annotations

import csv
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

# ── Config ────────────────────────────────────────────────────────────────

BASE_URL = "http://localhost:8000"
AREA = "America"
DOLLARS_PER_TRADE = 1000.0       # $1,000 per drop signal
DROP_THRESHOLD = -0.05           # -5 % close-to-close
MAX_TICKERS = 30                  # 0 = unlimited; set to e.g. 50 for a quick test
START_CAPITAL = 100_000.0
OUTPUT_DIR = Path("backtest_results")

# ── Data classes ──────────────────────────────────────────────────────────

@dataclass
class TickerResult:
    ticker: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_gain_per_day_pct: float = 0.0
    total_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    total_commission: float = 0.0
    gross_pnl: float = 0.0
    net_pnl: float = 0.0
    best_trade: dict[str, Any] | None = None
    worst_trade: dict[str, Any] | None = None
    signal_count: int = 0
    bar_count: int = 0
    first_date: str = ""
    last_date: str = ""
    raw_response: dict[str, Any] | None = None
    error: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────

def api_get(path: str, **params: Any) -> dict[str, Any] | None:
    """GET *path* with query params, return JSON or None on failure."""
    url = f"{BASE_URL}{path}"
    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        print(f"  [{resp.status_code}] GET {url} -- {resp.text[:120]}")
    except requests.RequestException as exc:
        print(f"  [!] GET {url} -- {exc}")
    return None


def api_post(path: str, body: dict[str, Any]) -> dict[str, Any] | None:
    """POST JSON *body* to *path*, return JSON or None on failure."""
    url = f"{BASE_URL}{path}"
    try:
        resp = requests.post(url, json=body, timeout=60)
        if resp.status_code == 200:
            return resp.json()
        print(f"  [{resp.status_code}] POST {url} -- {resp.text[:200]}")
    except requests.RequestException as exc:
        print(f"  [!] POST {url} -- {exc}")
    return None


def _pick_best_trade(closed_trades: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the trade with the highest *return_pct*."""
    if not closed_trades:
        return None
    return max(closed_trades, key=lambda t: t.get("return_pct", -999.0))


def _pick_worst_trade(closed_trades: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the trade with the lowest *return_pct*."""
    if not closed_trades:
        return None
    return min(closed_trades, key=lambda t: t.get("return_pct", 999.0))


# ── Signal detection ─────────────────────────────────────────────────────

def find_drop_signals(bars: list[dict[str, Any]]) -> tuple[dict[str, float], dict[str, int]]:
    """Scan *bars* for >5 % daily drops and return (buy_in, sell_out) maps.

    A "drop" means ``(close[t] - close[t-1]) / close[t-1] < -5 %``.
    Each buy is DOLLARS_PER_TRADE dollars (converted to shares by the
    server via ``buy_mode="dollars"``).  Each sell closes ALL accumulated
    shares from that signal 5 bars after the drop bar.
    """
    buy_in: dict[str, float] = {}       # date -> dollars
    sell_out: dict[str, int] = {}       # date -> shares  (filled below)
    pending_shares: dict[str, int] = {} # sell_date -> total shares

    n = len(bars)

    for i in range(1, n):
        prev_close = bars[i - 1]["close"]
        curr_close = bars[i]["close"]

        if prev_close == 0:
            continue

        change = (curr_close - prev_close) / prev_close

        if change < DROP_THRESHOLD:
            buy_idx = i + 1       # next trading day after the drop
            sell_idx = i + 5      # 5 trading days after the drop bar

            if buy_idx < n and sell_idx < n:
                buy_date = bars[buy_idx]["date"]
                sell_date = bars[sell_idx]["date"]
                open_price = bars[buy_idx]["open"]

                if open_price <= 0:
                    continue

                est_shares = int(DOLLARS_PER_TRADE / open_price)

                buy_in[buy_date] = buy_in.get(buy_date, 0.0) + DOLLARS_PER_TRADE
                pending_shares[sell_date] = pending_shares.get(sell_date, 0) + est_shares

    # Convert pending share counts to actual sell_out map (drop zeros)
    for sell_date, qty in pending_shares.items():
        if qty > 0:
            sell_out[sell_date] = qty

    # Also clean buy_in of any zero-effective entries
    buy_in = {d: v for d, v in buy_in.items() if v > 0}

    return buy_in, sell_out


# ── Persistence ───────────────────────────────────────────────────────────

def _serialise_result(r: TickerResult) -> dict[str, Any]:
    """Convert a TickerResult to a JSON-serialisable dict."""
    return {
        "ticker": r.ticker,
        "total_trades": r.total_trades,
        "winning_trades": r.winning_trades,
        "losing_trades": r.losing_trades,
        "win_rate": r.win_rate,
        "avg_gain_per_day_pct": r.avg_gain_per_day_pct,
        "total_return_pct": r.total_return_pct,
        "max_drawdown_pct": r.max_drawdown_pct,
        "total_commission": r.total_commission,
        "gross_pnl": r.gross_pnl,
        "net_pnl": r.net_pnl,
        "best_trade": r.best_trade,
        "worst_trade": r.worst_trade,
        "signal_count": r.signal_count,
        "bar_count": r.bar_count,
        "first_date": r.first_date,
        "last_date": r.last_date,
        "error": r.error,
    }


def save_results(results: list[TickerResult], output_dir: Path) -> None:
    """Persist full results as JSON and a flat CSV."""
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # JSON -- full detail
    json_path = output_dir / f"results_{stamp}.json"
    payload = {
        "generated": datetime.now().isoformat(),
        "config": {
            "area": AREA,
            "dollars_per_trade": DOLLARS_PER_TRADE,
            "drop_threshold": DROP_THRESHOLD,
            "start_capital": START_CAPITAL,
            "max_tickers": MAX_TICKERS,
        },
        "summary": _build_summary(results),
        "tickers": [_serialise_result(r) for r in results],
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nFull results saved -> {json_path}")

    # CSV -- one row per ticker  (flat, no nested trade detail)
    csv_path = output_dir / f"results_{stamp}.csv"
    fieldnames = [
        "ticker", "total_trades", "winning_trades", "losing_trades",
        "win_rate", "avg_gain_per_day_pct", "total_return_pct",
        "max_drawdown_pct", "total_commission", "gross_pnl", "net_pnl",
        "signal_count", "bar_count", "first_date", "last_date", "error",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in results:
            w.writerow(_serialise_result(r))
    print(f"CSV summary saved  -> {csv_path}")


def _build_summary(results: list[TickerResult]) -> dict[str, Any]:
    """Compute aggregate statistics across all tickers."""
    traded = [r for r in results if r.total_trades > 0]
    if not traded:
        return {"total_tickers_scanned": len(results), "tickers_with_trades": 0}

    all_returns = [r.total_return_pct for r in traded]
    all_win_rates = [r.win_rate for r in traded if r.total_trades >= 3]
    all_gain_per_day = [r.avg_gain_per_day_pct for r in traded]

    total_net = sum(r.net_pnl for r in traded)
    total_gross = sum(r.gross_pnl for r in traded)
    total_comm = sum(r.total_commission for r in traded)

    all_returns.sort()
    all_gain_per_day.sort()

    n = len(all_returns)
    p10 = all_returns[int(n * 0.10)] if n > 0 else 0.0
    p25 = all_returns[int(n * 0.25)] if n > 0 else 0.0
    p50 = all_returns[int(n * 0.50)] if n > 0 else 0.0
    p75 = all_returns[int(n * 0.75)] if n > 0 else 0.0
    p90 = all_returns[int(n * 0.90)] if n > 0 else 0.0

    return {
        "total_tickers_scanned": len(results),
        "tickers_with_trades": len(traded),
        "tickers_with_errors": sum(1 for r in results if r.error is not None),
        "total_trades_all_tickers": sum(r.total_trades for r in traded),
        "total_winning_trades": sum(r.winning_trades for r in traded),
        "total_losing_trades": sum(r.losing_trades for r in traded),
        "aggregate_gross_pnl": round(total_gross, 2),
        "aggregate_net_pnl": round(total_net, 2),
        "aggregate_total_commission": round(total_comm, 2),
        "mean_return_pct": round(sum(all_returns) / n, 2) if n else 0.0,
        "median_return_pct": round(p50, 2),
        "return_pct_p10": round(p10, 2),
        "return_pct_p25": round(p25, 2),
        "return_pct_p75": round(p75, 2),
        "return_pct_p90": round(p90, 2),
        "mean_gain_per_day_pct": round(sum(all_gain_per_day) / n, 3) if n else 0.0,
        "mean_win_rate": round(sum(all_win_rates) / len(all_win_rates), 4) if all_win_rates else 0.0,
    }


# ── Console report ────────────────────────────────────────────────────────

def print_report(results: list[TickerResult]) -> None:
    traded = [r for r in results if r.total_trades > 0]
    failed = [r for r in results if r.error is not None]

    if not traded:
        print("\nNo trades were generated across any ticker.")
        return

    # ── Aggregate P&L summary ────────────────────────────────────────
    total_net = sum(r.net_pnl for r in traded)
    total_gross = sum(r.gross_pnl for r in traded)
    total_comm = sum(r.total_commission for r in traded)
    total_tr = sum(r.total_trades for r in traded)
    total_win = sum(r.winning_trades for r in traded)
    total_loss = sum(r.losing_trades for r in traded)

    print()
    print("=" * 76)
    print("AGGREGATE P&L -- ALL TICKERS")
    print("=" * 76)
    print(f"  Tickers scanned:     {len(results):>8}")
    print(f"  Tickers with trades: {len(traded):>8}")
    print(f"  Tickers with errors: {len(failed):>8}")
    print(f"  Total trades:        {total_tr:>8}")
    print(f"  Winning trades:      {total_win:>8}  ({total_win/total_tr*100:.1f}%)" if total_tr else "")
    print(f"  Losing trades:       {total_loss:>8}  ({total_loss/total_tr*100:.1f}%)" if total_tr else "")
    print(f"  Gross P&L:          ${total_gross:>10,.2f}")
    print(f"  Total commission:   ${total_comm:>10,.2f}")
    print(f"  Net P&L:            ${total_net:>10,.2f}")
    print()

    # ── Distribution ──────────────────────────────────────────────────
    returns = sorted(r.total_return_pct for r in traded)
    n = len(returns)
    p10 = returns[int(n * 0.10)] if n > 1 else returns[0]
    p25 = returns[int(n * 0.25)] if n > 1 else returns[0]
    p50 = returns[int(n * 0.50)] if n > 1 else returns[0]
    p75 = returns[int(n * 0.75)] if n > 1 else returns[0]
    p90 = returns[int(n * 0.90)] if n > 1 else returns[0]
    positive = sum(1 for r in traded if r.total_return_pct > 0)

    print("=" * 76)
    print("RETURN DISTRIBUTION  (per-ticker total_return_pct)")
    print("=" * 76)
    print(f"  Mean:   {sum(returns)/n:>8.2f}%")
    print(f"  Median: {p50:>8.2f}%")
    print(f"  P10:    {p10:>8.2f}%")
    print(f"  P25:    {p25:>8.2f}%")
    print(f"  P75:    {p75:>8.2f}%")
    print(f"  P90:    {p90:>8.2f}%")
    print(f"  Min:    {returns[0]:>8.2f}%")
    print(f"  Max:    {returns[-1]:>8.2f}%")
    print(f"  Positive return: {positive}/{n} ({positive/n*100:.1f}%)")
    print()

    # ── Distribution buckets ───────────────────────────────────────────
    buckets = {
        "< -20%": 0,
        "-20% .. -10%": 0,
        "-10% .. -5%": 0,
        "-5% .. 0%": 0,
        "0% .. +5%": 0,
        "+5% .. +10%": 0,
        "+10% .. +20%": 0,
        "> +20%": 0,
    }
    for r in traded:
        v = r.total_return_pct
        if v < -20:       buckets["< -20%"] += 1
        elif v < -10:     buckets["-20% .. -10%"] += 1
        elif v < -5:      buckets["-10% .. -5%"] += 1
        elif v < 0:       buckets["-5% .. 0%"] += 1
        elif v < 5:       buckets["0% .. +5%"] += 1
        elif v < 10:      buckets["+5% .. +10%"] += 1
        elif v < 20:      buckets["+10% .. +20%"] += 1
        else:             buckets["> +20%"] += 1

    print("=" * 76)
    print("RETURN BUCKETS  (number of tickers per range)")
    print("=" * 76)
    max_bucket = max(buckets.values()) if buckets.values() else 1
    for label, count in buckets.items():
        bar = "#" * int(count / max_bucket * 40)
        print(f"  {label:>16s}  {count:>6d}  {bar}")
    print()

    # ── Top by avg gain per day ───────────────────────────────────────
    by_gain = sorted(traded, key=lambda r: r.avg_gain_per_day_pct, reverse=True)
    print("=" * 90)
    print("TOP 10 -- Highest average gain per day (%)")
    print("=" * 90)
    header = f"{'#':>3} {'Ticker':<8} {'Trades':>6} {'Win%':>8} {'Gain/Day%':>10} {'Return%':>10} {'NetP&L':>12} {'MaxDD%':>8}"
    print(header)
    print("-" * 90)
    for i, r in enumerate(by_gain[:10], 1):
        print(f"{i:>3} {r.ticker:<8} {r.total_trades:>6} {r.win_rate:>7.1%} "
              f"{r.avg_gain_per_day_pct:>10.3f} {r.total_return_pct:>9.2f}% "
              f"${r.net_pnl:>10,.2f} {r.max_drawdown_pct:>7.2f}%")

    # ── Top by win rate (min 3 trades) ────────────────────────────────
    min_trades = 3
    by_winrate = sorted(
        [r for r in traded if r.total_trades >= min_trades],
        key=lambda r: (r.win_rate, r.total_trades),
        reverse=True,
    )
    print()
    print("=" * 90)
    print(f"TOP 10 -- Highest win rate  (min {min_trades} trades)")
    print("=" * 90)
    print(header)
    print("-" * 90)
    if by_winrate:
        for i, r in enumerate(by_winrate[:10], 1):
            print(f"{i:>3} {r.ticker:<8} {r.total_trades:>6} {r.win_rate:>7.1%} "
                  f"{r.avg_gain_per_day_pct:>10.3f} {r.total_return_pct:>9.2f}% "
                  f"${r.net_pnl:>10,.2f} {r.max_drawdown_pct:>7.2f}%")
    else:
        print("  (none with enough trades)")

    # ── Top by net P&L ────────────────────────────────────────────────
    by_pnl = sorted(traded, key=lambda r: r.net_pnl, reverse=True)
    print()
    print("=" * 90)
    print("TOP 10 -- Highest net P&L ($)")
    print("=" * 90)
    print(header)
    print("-" * 90)
    for i, r in enumerate(by_pnl[:10], 1):
        print(f"{i:>3} {r.ticker:<8} {r.total_trades:>6} {r.win_rate:>7.1%} "
              f"{r.avg_gain_per_day_pct:>10.3f} {r.total_return_pct:>9.2f}% "
              f"${r.net_pnl:>10,.2f} {r.max_drawdown_pct:>7.2f}%")

    # ── Worst by net P&L ──────────────────────────────────────────────
    by_worst = sorted(traded, key=lambda r: r.net_pnl)
    print()
    print("=" * 90)
    print("BOTTOM 5 -- Lowest net P&L ($)")
    print("=" * 90)
    print(header)
    print("-" * 90)
    for i, r in enumerate(by_worst[:5], 1):
        print(f"{i:>3} {r.ticker:<8} {r.total_trades:>6} {r.win_rate:>7.1%} "
              f"{r.avg_gain_per_day_pct:>10.3f} {r.total_return_pct:>9.2f}% "
              f"${r.net_pnl:>10,.2f} {r.max_drawdown_pct:>7.2f}%")

    # ── Best single trades from top-5 gain/day tickers ────────────────
    print()
    print("=" * 76)
    print("Best individual trade detail -- top 5 gain/day tickers")
    print("=" * 76)

    for r in by_gain[:5]:
        print(f"\n  {r.ticker}  ({r.total_trades} trades, "
              f"avg +{r.avg_gain_per_day_pct:.3f}%/day, "
              f"win rate {r.win_rate:.1%}, "
              f"net P&L ${r.net_pnl:,.2f})")
        if r.best_trade:
            bt = r.best_trade
            print(f"    Best trade:  buy  {bt['buy_date']}  @ ${bt['buy_price']:.2f}  x{bt['total_quantity']}")
            print(f"                 sell {bt['sell_date']}  @ ${bt['sell_price']:.2f}")
            print(f"                 net P&L ${bt['net_pnl']:,.2f}  |  "
                  f"+{bt['return_pct']:.2f}%  |  {bt['days_held']} days  |  "
                  f"+{bt['gain_per_day_pct']:.3f}%/day")
            if bt.get("extra_buys"):
                for eb in bt["extra_buys"]:
                    print(f"                 `- also bought {eb['buy_date']} @ ${eb['buy_price']:.2f}  x{eb['quantity']}")
        else:
            print("    (no trade detail available)")

        if r.worst_trade:
            wt = r.worst_trade
            print(f"    Worst trade: buy  {wt['buy_date']}  @ ${wt['buy_price']:.2f}  x{wt['total_quantity']}")
            print(f"                 sell {wt['sell_date']}  @ ${wt['sell_price']:.2f}")
            print(f"                 net P&L ${wt['net_pnl']:,.2f}  |  "
                  f"{wt['return_pct']:.2f}%  |  {wt['days_held']} days")

    print()
    print("Done.")


# ── Main loop ─────────────────────────────────────────────────────────────

def main() -> None:
    # 1. Fetch ticker list ─────────────────────────────────────────────────
    print("Fetching ticker list ...", end=" ", flush=True)
    data = api_get(f"/api/tickers/{AREA}")
    if data is None:
        print("FAILED -- is the backtest server running?")
        sys.exit(1)

    all_tickers: list[str] = data["tickers"]
    total = len(all_tickers)
    print(f"{total} tickers found.")

    if MAX_TICKERS > 0:
        all_tickers = all_tickers[:MAX_TICKERS]
        print(f"Limited to first {len(all_tickers)} tickers.")
    print()

    # 2. Process each ticker ───────────────────────────────────────────────
    results: list[TickerResult] = []
    t_start = time.time()

    for idx, ticker in enumerate(all_tickers, 1):
        pct = idx / len(all_tickers) * 100
        elapsed = time.time() - t_start
        rate = idx / elapsed if elapsed > 0 else 0
        eta = (len(all_tickers) - idx) / rate / 60 if rate > 0 else 0
        print(f"\r[{idx}/{len(all_tickers)} {pct:.0f}%  {rate:.1f} ticker/s  ETA {eta:.0f}m] {ticker:<8}", end="", flush=True)

        # Get bars for this ticker
        bars_data = api_get(f"/api/{AREA}/{ticker}")
        if bars_data is None:
            results.append(TickerResult(ticker=ticker, error="no bar data"))
            continue

        bars = bars_data.get("bars", [])
        if len(bars) < 7:          # need at least a week of data
            results.append(TickerResult(ticker=ticker, error="too few bars"))
            continue

        # Find drop-rebound signals
        buy_in, sell_out = find_drop_signals(bars)
        signal_count = len(buy_in)

        if not buy_in or not sell_out:
            results.append(TickerResult(
                ticker=ticker,
                bar_count=len(bars),
                first_date=bars[0]["date"] if bars else "",
                last_date=bars[-1]["date"] if bars else "",
                error="no signals",
            ))
            continue

        # Run backtest in dollars mode
        bt = api_post(f"/api/{AREA}/{ticker}/backtest", {
            "start_capital": START_CAPITAL,
            "buy_mode": "dollars",
            "buy_in": buy_in,
            "sell_out": sell_out,
        })
        if bt is None:
            results.append(TickerResult(
                ticker=ticker,
                bar_count=len(bars),
                first_date=bars[0]["date"] if bars else "",
                last_date=bars[-1]["date"] if bars else "",
                signal_count=signal_count,
                error="backtest failed",
            ))
            continue

        trades = bt.get("closed_trades", [])
        total_trades = bt.get("total_trades", 0)

        results.append(TickerResult(
            ticker=ticker,
            total_trades=total_trades,
            winning_trades=sum(1 for t in trades if t.get("net_pnl", 0) > 0),
            losing_trades=sum(1 for t in trades if t.get("net_pnl", 0) <= 0),
            win_rate=bt.get("win_rate", 0.0),
            avg_gain_per_day_pct=bt.get("avg_gain_per_day_pct", 0.0),
            total_return_pct=bt.get("total_return_pct", 0.0),
            max_drawdown_pct=bt.get("max_drawdown_pct", 0.0),
            total_commission=bt.get("total_commission", 0.0),
            gross_pnl=sum(t.get("gross_pnl", 0.0) for t in trades),
            net_pnl=sum(t.get("net_pnl", 0.0) for t in trades),
            best_trade=_pick_best_trade(trades),
            worst_trade=_pick_worst_trade(trades),
            signal_count=signal_count,
            bar_count=len(bars),
            first_date=bars[0]["date"] if bars else "",
            last_date=bars[-1]["date"] if bars else "",
            raw_response=bt,
        ))

    elapsed_total = time.time() - t_start
    print(f"\n\nDone in {elapsed_total/60:.1f} min.  Processed {len(results)} tickers.\n")

    # 3. Console report ────────────────────────────────────────────────────
    print_report(results)

    # 4. Save to disk ──────────────────────────────────────────────────────
    save_results(results, OUTPUT_DIR)


if __name__ == "__main__":
    main()
