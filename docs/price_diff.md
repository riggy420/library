# price_diff — OHLCV Price Difference Calculator

Computes percentage and absolute differences over an OHLCV series and
saves the enriched data alongside the original CSV files.

---

## File Formats

### Input format (scraper output)

Files created by `scrapper.py` live under `stock_data/{area}/{TICKER}.txt`.

**No header row.**  Quoted CSV (`QUOTE_NONNUMERIC`).  Six columns:

```
"Date","Close","High","Low","Open","Volume"
```

| # | Column | Type | Example |
|---|--------|------|---------|
| 1 | Date | `YYYY-MM-DD` | `"2021-07-19"` |
| 2 | Close | float | `2.91` |
| 3 | High | float | `2.99` |
| 4 | Low | float | `2.65` |
| 5 | Open | float | `2.98` |
| 6 | Volume | int | `650200` |

**Sample rows:**

```
"2021-07-19","2.91","2.99","2.65","2.98","650200"
"2021-07-20","3.02","3.30","2.90","3.28","377300"
"2021-07-21","3.25","3.41","3.14","3.19","278800"
```

### Output format (modified)

Files written to `{area}_modified[_Nd]/` keep the same quoting convention
with **12 extra columns appended** after Volume.  No header.

```
"Date","Close","High","Low","Open","Volume",<12 diff columns>
```

**Row 1** (and the first *N* rows when `--interval N` > 1) have
**empty strings** (`""`) for all diff columns because there is no prior
bar to compare against.

**Sample row with interval=1 (daily):**

```
"2021-07-20","3.02","3.30","2.90","3.28","377300",-6.27,-0.19,2.68,0.08,...
```

### Diff columns (12 extra fields)

When `--interval 1` (daily, default) the column names are:

| # | Column | Formula |
|---|--------|---------|
| 7 | `pct_chg` | `(close[t] - close[t-1]) / close[t-1] * 100` |
| 8 | `abs_chg` | `close[t] - close[t-1]` |
| 9 | `gap_pct` | `(open[t] - close[t-1]) / close[t-1] * 100` |
| 10 | `gap_abs` | `open[t] - close[t-1]` |
| 11 | `range_pct` | `(high[t] - low[t]) / low[t] * 100` |
| 12 | `range_abs` | `high[t] - low[t]` |
| 13 | `co_pct` | `(close[t] - open[t]) / open[t] * 100` |
| 14 | `co_abs` | `close[t] - open[t]` |
| 15 | `high_from_close_pct` | `(high[t] - close[t]) / close[t] * 100` |
| 16 | `low_from_close_pct` | `(low[t] - close[t]) / close[t] * 100` |
| 17 | `vol_chg_pct` | `(volume[t] - volume[t-1]) / volume[t-1] * 100` |
| 18 | `drawdown_pct` | `(close[t] - cummax_close[t]) / cummax_close[t] * 100` |

When `--interval N` (N > 1) the columns are **suffixed** with `_Nd`.
For example with `--interval 5`:

```
pct_chg_5d, abs_chg_5d, gap_pct_5d, gap_abs_5d, range_pct_5d,
range_abs_5d, co_pct_5d, co_abs_5d, high_from_close_pct_5d,
low_from_close_pct_5d, vol_chg_pct_5d, drawdown_pct_5d
```

The suffix tags the lookback window so different-interval outputs can
coexist on disk without overwriting each other.

### Output directory naming

| Command | Output path |
|---------|-------------|
| `--batch America` | `America_modified/` |
| `--batch America -i 5` | `America_modified_5d/` |
| `--batch America -i 21` | `America_modified_21d/` |
| `--batch America -i 5 --outdir my_dir` | `my_dir/` |

---

## CLI Reference

```
python price_diff.py [TICKERS...] [FLAGS]
```

### Positional arguments

| Arg | Description |
|-----|-------------|
| `TICKERS` | One or more stock symbols, space-separated.  Omit with `--batch`. |

### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--area AREA` | `America` | Market area (`America`, `SS`, `SZ`) |
| `--since DATE` | 5yr ago | Start date `YYYY-MM-DD` |
| `--until DATE` | today | End date `YYYY-MM-DD` |
| `--interval N`, `-i N` | `1` | Lookback in bars: `1` = daily, `5` = weekly, `21` = monthly |
| `--summary` | — | Print aggregate stats (mean, median, std, min, max) |
| `--moves PCT` | — | Show rows where `abs(pct_chg) >= PCT%` |
| `--gaps N` | — | Show top-N biggest overnight gap days |
| `--json` | — | Output as JSON |
| `--csv` | — | Output as CSV to stdout |
| `--batch` | — | Process **all** tickers in the area and save to disk |
| `--max N` | `0` (all) | Limit `--batch` to N tickers |
| `--outdir DIR` | auto | Override output directory for `--batch` |

### Examples

```bash
# Single ticker — summary statistics (daily)
python price_diff.py AAPL --summary

# Single ticker — weekly changes
python price_diff.py AAPL --summary --interval 5

# Multiple tickers
python price_diff.py AAPL TSLA MSFT --summary

# Filter by date range
python price_diff.py AAPL --summary --since 2025-01-01 --until 2025-12-31

# Find big moves (>= 5%)
python price_diff.py AAPL --moves 5 --since 2025-01-01

# Top-10 biggest overnight gaps
python price_diff.py AAPL --gaps 10

# Export to CSV
python price_diff.py AAPL --csv --since 2025-01-01 > aapl_diffs.csv

# Export to JSON
python price_diff.py AAPL --json > aapl_diffs.json

# Batch — process all 4,043 America tickers (daily)
python price_diff.py --batch America

# Batch — first 100 tickers, weekly interval
python price_diff.py --batch America --max 100 --interval 5

# Batch — custom output directory
python price_diff.py --batch America --interval 21 --outdir my_monthly_diffs
```

### Library API

```python
from price_diff import compute_diffs, summary, large_moves, batch_process
import pandas as pd

# From a DataFrame
df = pd.read_csv("stock_data/America/AAPL.txt", header=None,
                 names=["Date","Close","High","Low","Open","Volume"],
                 quoting=1, on_bad_lines="skip")
df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

# Daily diffs
result = compute_diffs(df)                # interval=1
stats  = summary(result)                  # aggregate stats dict
hits   = large_moves(result, 5.0)         # days with abs(chg) >= 5%

# Weekly diffs
result_5d = compute_diffs(df, interval=5)

# From bar dicts
bars = [{"date":"2025-01-02","open":100.0,"high":103.0,
         "low":99.0,"close":102.0,"volume":1000000}, ...]
result = compute_diffs(bars)

# Batch — process all tickers
batch_process("America", interval=5, max_tickers=100)
```

### Fallback data sources

The CLI tries the backtest server first (`http://localhost:8000`).  If the
server is not running it falls back to reading `stock_data/{area}/{TICKER}.txt`
directly from disk.

---

## Column Description Quick Reference

| Column | What it measures | Typical use |
|--------|-----------------|-------------|
| `pct_chg` | Close-to-close return % | Trend, momentum, signal detection |
| `abs_chg` | Close-to-close dollar move | Dollar-denominated analysis |
| `gap_pct` | Overnight gap % (open vs prior close) | Gap trading, earnings reactions |
| `range_pct` | Intraday range % | Volatility filtering |
| `co_pct` | Close-vs-open % (intraday drift) | Day-trade evaluation |
| `high_from_close_pct` | How far above close the high was | Stop-loss placement |
| `low_from_close_pct` | How far below close the low was | Stop-loss placement |
| `vol_chg_pct` | Volume surge/contraction % | Volume confirmation |
| `drawdown_pct` | Decline from running max close % | Risk management, max pain |
