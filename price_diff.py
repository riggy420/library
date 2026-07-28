"""
price_diff.py — OHLCV price differences and percentage-change calculator.

Works both as a **standalone library** (operates on pandas DataFrames or
lists of bar dicts) and as a **CLI tool** that reads from the backtest
server and prints a summary.

Usage (library)::

    from price_diff import compute_diffs, DIFF_COLUMNS
    df = compute_diffs(bars_df)
    # df now has extra columns: pct_chg, gap_pct, range_pct, ...

Usage (CLI)::

    python price_diff.py AAPL                      # last 5 years, tabular
    python price_diff.py AAPL --json               # JSON output
    python price_diff.py AAPL --csv > aapl.csv     # CSV to stdout
    python price_diff.py AAPL --since 2025-01-01   # filtered range
    python price_diff.py --batch America           # process ALL tickers in area
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

# ── Column definitions ────────────────────────────────────────────────────

#: All computed difference columns (names and descriptions).
DIFF_COLUMNS: dict[str, str] = {
    # Daily close-to-close
    "pct_chg":          "Close % change vs prior day: (close[t] - close[t-1]) / close[t-1] * 100",
    "abs_chg":          "Close absolute change vs prior day: close[t] - close[t-1]",
    # Gap
    "gap_pct":          "Open vs prior close %: (open[t] - close[t-1]) / close[t-1] * 100",
    "gap_abs":          "Open vs prior close absolute: open[t] - close[t-1]",
    # Intraday
    "range_pct":        "Intraday range %: (high[t] - low[t]) / low[t] * 100",
    "range_abs":        "Intraday range absolute: high[t] - low[t]",
    # Close vs open
    "co_pct":           "Close vs open %: (close[t] - open[t]) / open[t] * 100",
    "co_abs":           "Close vs open absolute: close[t] - open[t]",
    # High / low vs close
    "high_from_close_pct": "High above close %: (high[t] - close[t]) / close[t] * 100",
    "low_from_close_pct":  "Low below close %: (low[t] - close[t]) / close[t] * 100",
    # Volume
    "vol_chg_pct":      "Volume % change vs prior day: (vol[t] - vol[t-1]) / vol[t-1] * 100",
    # Cumulative (useful for max drawdown calculations)
    "cummax_close":     "Running maximum close to date",
    "drawdown_pct":     "Drawdown from running max: (close - cummax) / cummax * 100",
}


# ── Core computation ──────────────────────────────────────────────────────

def compute_diffs(
    data: pd.DataFrame | list[dict],
    date_col: str = "date",
    sort: bool = True,
    interval: int = 1,
) -> pd.DataFrame:
    """Compute all percentage and absolute differences for an OHLCV series.

    Args:
        data: Either a ``pd.DataFrame`` with columns
              ``[date, open, high, low, close, volume]`` (case-insensitive),
              or a list of bar dicts like
              ``[{"date":..., "open":..., ...}, ...]``.
        date_col: Name of the date column.
        sort: If ``True``, sort by date ascending before computing.
        interval: Lookback in **bars**.  ``1`` = day-over-day (default);
            ``5`` = week-over-week; ``21`` = month-over-month.

    Returns:
        A DataFrame with the original columns plus all computed columns
        listed in :data:`DIFF_COLUMNS`.
    """
    if interval < 1:
        raise ValueError(f"interval must be >= 1, got {interval}")

    df = _to_dataframe(data, date_col)
    if df.empty:
        return df

    if sort and date_col in df.columns:
        df = df.sort_values(date_col).reset_index(drop=True)

    # Normalise column names to lowercase
    _map = _normalise_columns(df)
    o, h, l, c, v = _map["open"], _map["high"], _map["low"], _map["close"], _map["volume"]
    dcol = _map.get("date", date_col)

    # Tag column names with interval suffix when > 1
    tag = f"_{interval}d" if interval > 1 else ""

    # Prior values at *interval* bars back
    prev_c = df[c].shift(interval)
    prev_v = df[v].shift(interval)

    # -- close-to-close over interval -------------------------------------------
    df[f"pct_chg{tag}"] = ((df[c] - prev_c) / prev_c * 100).round(4)
    df[f"abs_chg{tag}"] = (df[c] - prev_c).round(4)

    # -- gap (open vs prior close) ----------------------------------------------
    # For interval > 1, gap is open[t] vs close[t-interval]
    df[f"gap_pct{tag}"] = ((df[o] - prev_c) / prev_c * 100).round(4)
    df[f"gap_abs{tag}"] = (df[o] - prev_c).round(4)

    # -- intraday range (same-day; interval doesn't affect this) ----------------
    df[f"range_pct{tag}"] = ((df[h] - df[l]) / df[l] * 100).round(4)
    df[f"range_abs{tag}"] = (df[h] - df[l]).round(4)

    # -- close vs open (same-day; interval doesn't affect this) -----------------
    df[f"co_pct{tag}"] = ((df[c] - df[o]) / df[o] * 100).round(4)
    df[f"co_abs{tag}"] = (df[c] - df[o]).round(4)

    # -- high / low vs close (same-day) -----------------------------------------
    df[f"high_from_close_pct{tag}"] = ((df[h] - df[c]) / df[c] * 100).round(4)
    df[f"low_from_close_pct{tag}"] = ((df[l] - df[c]) / df[c] * 100).round(4)

    # -- volume change over interval --------------------------------------------
    df[f"vol_chg_pct{tag}"] = ((df[v] - prev_v) / prev_v * 100).round(4)

    # -- cumulative max and drawdown --------------------------------------------
    df[f"cummax_close{tag}"] = df[c].cummax()
    df[f"drawdown_pct{tag}"] = ((df[c] - df[f"cummax_close{tag}"]) / df[f"cummax_close{tag}"] * 100).round(4)

    # Restore original column casing
    if dcol != "date" and "date" not in df.columns:
        df.rename(columns={"date": dcol}, inplace=True)

    return df


# ── Aggregation helpers ───────────────────────────────────────────────────

def summary(df: pd.DataFrame, interval: int = 1) -> dict:
    """Return a dict of aggregate statistics over the computed columns.

    Only rows where the pct_chg column is not NaN are included.
    """
    tag = f"_{interval}d" if interval > 1 else ""
    pct_col = f"pct_chg{tag}"
    dd_col = f"drawdown_pct{tag}"

    if pct_col not in df.columns:
        return {"error": f"column '{pct_col}' not found — run compute_diffs(interval={interval}) first"}

    d = df.dropna(subset=[pct_col])
    if d.empty:
        return {"warning": "insufficient data (need >= 2 rows)"}

    def _p(vals) -> dict:
        v = vals.dropna()
        if len(v) == 0:
            return {}
        return {
            "mean": round(float(v.mean()), 4),
            "median": round(float(v.median()), 4),
            "std": round(float(v.std()), 4),
            "min": round(float(v.min()), 4),
            "max": round(float(v.max()), 4),
        }

    cols = {
        "pct_chg": f"pct_chg{tag}",
        "gap_pct": f"gap_pct{tag}",
        "range_pct": f"range_pct{tag}",
        "co_pct": f"co_pct{tag}",
        "vol_chg_pct": f"vol_chg_pct{tag}",
    }

    out: dict = {
        "rows": len(d),
        "interval": interval,
        "date_range": {
            "first": str(d.iloc[0].get("date", "")),
            "last": str(d.iloc[-1].get("date", "")),
        },
    }
    for key, col in cols.items():
        if col in d.columns:
            out[key] = _p(d[col])
    if dd_col in d.columns:
        out["drawdown_pct_min"] = round(float(d[dd_col].min()), 4)

    return out


def large_moves(df: pd.DataFrame, threshold_pct: float = 5.0,
                interval: int = 1) -> pd.DataFrame:
    """Return rows where ``abs(pct_chg) >= threshold_pct``, sorted by
    magnitude descending."""
    tag = f"_{interval}d" if interval > 1 else ""
    pct_col = f"pct_chg{tag}"
    d = df.dropna(subset=[pct_col]).copy()
    d["abs_pct"] = d[pct_col].abs()
    return d[d["abs_pct"] >= threshold_pct].sort_values("abs_pct", ascending=False)


def biggest_gaps(df: pd.DataFrame, n: int = 10,
                 interval: int = 1) -> pd.DataFrame:
    """Return the *n* rows with the largest absolute gap percentage."""
    tag = f"_{interval}d" if interval > 1 else ""
    gap_col = f"gap_pct{tag}"
    d = df.dropna(subset=[gap_col]).copy()
    d["abs_gap"] = d[gap_col].abs()
    return d.nlargest(n, "abs_gap")


# ── Internal helpers ──────────────────────────────────────────────────────

def _to_dataframe(data: pd.DataFrame | list[dict], date_col: str) -> pd.DataFrame:
    """Normalise input to a DataFrame with lowercase column names."""
    if isinstance(data, pd.DataFrame):
        df = data.copy()
    elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        df = pd.DataFrame(data)
    else:
        raise TypeError("data must be a pd.DataFrame or list[dict]")

    # Standardise column casing
    rename = {}
    for col in df.columns:
        rename[col] = col.lower()
    df.rename(columns=rename, inplace=True)

    if date_col.lower() in df.columns:
        df[date_col.lower()] = pd.to_datetime(df[date_col.lower()], errors="coerce")

    return df


def _normalise_columns(df: pd.DataFrame) -> dict[str, str]:
    """Map canonical names (open/high/low/close/volume) to actual column names."""
    out: dict[str, str] = {}
    for col in df.columns:
        low = col.lower()
        if low in ("open", "high", "low", "close", "volume", "date"):
            out[low] = col
    return out


# ── Batch processing ──────────────────────────────────────────────────────

def batch_process(
    area: str = "America",
    data_dir: str = "stock_data",
    output_dir: str | None = None,
    max_tickers: int = 0,
    interval: int = 1,
) -> dict:
    """Compute diffs for every ticker in an area and save to disk.

    Reads ``{data_dir}/{area}/{TICKER}.txt``, computes all diff columns,
    and writes ``{output_dir}/{TICKER}.txt``.  The output format mirrors
    the original CSV but with the extra columns appended as additional
    comma-separated fields (no header, QUOTE_NONNUMERIC).

    Args:
        area: Market area name (``"America"``, ``"SS"``, ``"SZ"``).
        data_dir: Root directory containing the per-area stock CSVs.
        output_dir: Where to write output files.  Defaults to
            ``{area}_modified/``.
        max_tickers: If > 0, stop after this many tickers (for testing).
        interval: Lookback in bars (1 = daily, 5 = weekly, 21 = monthly).

    Returns:
        ``{"processed": N, "skipped": N, "errors": N, "output_dir": "..."}``
    """
    import csv

    src_dir = Path(data_dir) / area
    if output_dir is None:
        tag = f"_{interval}d" if interval > 1 else ""
        output_dir = f"{area}_modified{tag}"
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    files = sorted(src_dir.glob("*.txt"))
    if not files:
        print(f"No .txt files found in {src_dir}")
        return {"processed": 0, "skipped": 0, "errors": 0, "output_dir": str(out_path)}

    processed = 0
    skipped = 0
    errors = 0
    total = len(files) if max_tickers <= 0 else min(len(files), max_tickers)

    for i, filepath in enumerate(files, 1):
        ticker = filepath.stem
        if max_tickers > 0 and i > max_tickers:
            break

        print(f"\r[{i}/{total}] {ticker:<8}", end="", flush=True)

        try:
            df = pd.read_csv(
                filepath,
                header=None,
                names=["Date", "Close", "High", "Low", "Open", "Volume"],
                quoting=csv.QUOTE_NONNUMERIC,
                on_bad_lines="skip",
            )
            df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d", errors="coerce")
            df = df.dropna(subset=["Date"]).sort_values("Date")

            if len(df) < 2:
                skipped += 1
                continue

            result = compute_diffs(df, interval=interval)

            tag = f"_{interval}d" if interval > 1 else ""

            # Build output: date,close,high,low,open,volume,<diff columns>
            diff_cols = [
                f"pct_chg{tag}", f"abs_chg{tag}",
                f"gap_pct{tag}", f"gap_abs{tag}",
                f"range_pct{tag}", f"range_abs{tag}",
                f"co_pct{tag}", f"co_abs{tag}",
                f"high_from_close_pct{tag}", f"low_from_close_pct{tag}",
                f"vol_chg_pct{tag}", f"drawdown_pct{tag}",
            ]
            # compute_diffs lowercases column names
            base_cols = ["date", "close", "high", "low", "open", "volume"]
            out_cols = base_cols + [c for c in diff_cols if c in result.columns]

            out_df = result[out_cols].copy()
            # Format the date back to string
            out_df["date"] = out_df["date"].dt.strftime("%Y-%m-%d")
            # Capitalise base column names to match original scraper format
            rename_back = {
                "date": "Date", "close": "Close", "high": "High",
                "low": "Low", "open": "Open", "volume": "Volume",
            }
            out_df.rename(columns=rename_back, inplace=True)

            # Round all float columns
            float_cols = out_df.select_dtypes(include="float").columns
            out_df[float_cols] = out_df[float_cols].round(4)
            # Write NaN as empty string
            out_df = out_df.fillna("")

            dest = out_path / f"{ticker}.txt"
            out_df.to_csv(
                dest,
                header=False,
                index=False,
                quoting=csv.QUOTE_NONNUMERIC,
            )
            processed += 1

        except Exception as exc:
            print(f"\n  [!] {ticker}: {exc}")
            errors += 1

    print(f"\rDone.  processed={processed}  skipped={skipped}  errors={errors}  "
          f"output -> {out_path}")

    return {
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
        "output_dir": str(out_path),
    }


# ── CLI ───────────────────────────────────────────────────────────────────

def _fetch_bars(ticker: str, area: str = "America",
                since: Optional[str] = None, until: Optional[str] = None) -> list[dict]:
    """Fetch OHLCV bars from the backtest server."""
    import requests

    params = {}
    if since:
        params["start_range"] = since
    if until:
        params["end_range"] = until

    url = f"http://localhost:8000/api/{area}/{ticker}"
    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("bars", [])
        print(f"Server returned {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
    except requests.RequestException as exc:
        print(f"Could not reach backtest server: {exc}", file=sys.stderr)

    # Fallback: try local CSV
    csv_path = Path(f"stock_data/{area}/{ticker}.txt")
    if csv_path.exists():
        df = pd.read_csv(csv_path, header=None,
                         names=["Date", "Close", "High", "Low", "Open", "Volume"],
                         quoting=csv.QUOTE_NONNUMERIC, on_bad_lines="skip")
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).sort_values("Date")
        bars = []
        for _, row in df.iterrows():
            bars.append({
                "date": row["Date"].strftime("%Y-%m-%d"),
                "open": float(row["Open"]), "high": float(row["High"]),
                "low": float(row["Low"]), "close": float(row["Close"]),
                "volume": int(row["Volume"]),
            })
        return bars

    return []


def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="OHLCV price difference calculator")
    parser.add_argument("tickers", nargs="*", default=None,
                        help="Stock ticker(s) — one or more, e.g. AAPL TSLA MSFT")
    parser.add_argument("--area", default="America", help="Market area (default: America)")
    parser.add_argument("--since", default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--until", default=None, help="End date YYYY-MM-DD")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--csv", action="store_true", help="Output as CSV")
    parser.add_argument("--summary", action="store_true", help="Print aggregate summary only")
    parser.add_argument("--moves", type=float, default=None, metavar="PCT",
                        help="Show moves >= PCT% (e.g. --moves 5)")
    parser.add_argument("--gaps", type=int, default=None, metavar="N",
                        help="Show top-N biggest gaps")
    parser.add_argument("--interval", "-i", type=int, default=1, metavar="N",
                        help="Lookback in bars: 1=daily, 5=weekly, 21=monthly (default: 1)")
    parser.add_argument("--batch", action="store_true",
                        help="Process ALL tickers and save to {area}_modified[_Nd]/")
    parser.add_argument("--max", type=int, default=0, metavar="N",
                        help="Limit batch to N tickers (for testing)")
    parser.add_argument("--outdir", default=None,
                        help="Override output directory (default: {area}_modified[_Nd]/)")
    args = parser.parse_args()

    interval = max(1, args.interval)

    # --batch mode: process all tickers
    if args.batch:
        result = batch_process(
            area=args.area,
            output_dir=args.outdir,
            max_tickers=args.max,
            interval=interval,
        )
        print(f"Output: {result['output_dir']}")
        return

    if not args.tickers:
        parser.error("must specify at least one ticker or use --batch")

    tag = f"_{interval}d" if interval > 1 else ""

    for ticker in args.tickers:
        bars = _fetch_bars(ticker, args.area, args.since, args.until)
        if not bars:
            print(f"No data found for {ticker} in {args.area}", file=sys.stderr)
            continue

        df = compute_diffs(bars, interval=interval)

        if len(args.tickers) > 1:
            print(f"\n--- {ticker} ---")

        if args.summary:
            s = summary(df, interval=interval)
            if args.json:
                s["ticker"] = ticker
                print(json.dumps(s, indent=2))
            else:
                print(f"\n  {ticker}  —  {len(df)} bars  "
                      f"({df.iloc[0].get('date','')} .. {df.iloc[-1].get('date','')})\n")
                for key, val in s.items():
                    if isinstance(val, dict) and "mean" in val:
                        print(f"  {key:>20s}  mean={val['mean']:>8.4f}  "
                              f"median={val['median']:>8.4f}  "
                              f"std={val['std']:>8.4f}  "
                              f"min={val['min']:>8.4f}  max={val['max']:>8.4f}")
        elif args.moves is not None:
            hits = large_moves(df, args.moves, interval=interval)
            if args.json:
                print(hits[["date", "open", "high", "low", "close", "volume",
                            f"pct_chg{tag}", f"gap_pct{tag}", f"range_pct{tag}",
                            f"co_pct{tag}"]].to_json(orient="records", indent=2))
            else:
                print(f"\n  {len(hits)} moves >= {args.moves}%  ({ticker})\n")
                print(f"{'Date':>12s}  {'Close':>10s}  {'Chg%':>8s}  {'Gap%':>8s}  "
                      f"{'Range%':>8s}  {'CO%':>8s}")
                for _, r in hits.iterrows():
                    print(f"{r['date']!s:>12s}  {r['close']:>10.2f}  "
                          f"{r[f'pct_chg{tag}']:>8.2f}  {r[f'gap_pct{tag}']:>8.2f}  "
                          f"{r[f'range_pct{tag}']:>8.2f}  {r[f'co_pct{tag}']:>8.2f}")
        elif args.gaps is not None:
            gaps = biggest_gaps(df, args.gaps, interval=interval)
            if args.json:
                print(gaps[["date", "open", "high", "low", "close",
                            f"gap_pct{tag}", f"gap_abs{tag}"]].to_json(orient="records", indent=2))
            else:
                print(f"\n  Top-{args.gaps} biggest gaps  ({ticker})\n")
                for _, r in gaps.iterrows():
                    print(f"  {r['date']!s}  open={r['open']:.2f}  "
                          f"prev_close={r['close'] - r[f'gap_abs{tag}']:.2f}  "
                          f"gap={r[f'gap_pct{tag}']:+.2f}%  (${r[f'gap_abs{tag}']:+.2f})")
        elif args.json:
            round_cols = [c for c in df.columns
                          if c in DIFF_COLUMNS or c in ("open", "high", "low", "close")]
            out = df[round_cols].round(4).to_dict(orient="records")
            print(json.dumps(out, indent=2))
        elif args.csv:
            df.to_csv(sys.stdout, index=False)
        else:
            s = summary(df, interval=interval)
            print(f"\n  {ticker}  —  {len(df)} bars  "
                  f"({df.iloc[0].get('date','')} .. {df.iloc[-1].get('date','')})\n")
            print(f"{'Metric':>22s}  {'Mean':>8s}  {'Median':>8s}  "
                  f"{'Std':>8s}  {'Min':>8s}  {'Max':>8s}")
            print("-" * 65)
            for key, val in s.items():
                if isinstance(val, dict) and "mean" in val:
                    print(f"  {key:>20s}  {val['mean']:>8.4f}  {val['median']:>8.4f}  "
                          f"{val['std']:>8.4f}  {val['min']:>8.4f}  {val['max']:>8.4f}")
            print(f"\n  drawdown (max): {s.get('drawdown_pct_min', 0):.2f}%")


if __name__ == "__main__":
    _cli()
