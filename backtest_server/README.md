'# Backtest Server

A lightweight **FastAPI** server for historical stock data lookup and batch backtesting. It reads OHLCV data from the scraped CSV files in `stock_data/` and exposes two core endpoints — one for fetching bars, one for simulating buy/sell orders and computing performance statistics.

## Quick Start

```bash
# Install dependencies (FastAPI + uvicorn)
pip install fastapi uvicorn

# Start the server
python -m backtest_server.main
```

Server is now running at **http://localhost:8000**.

- Interactive API docs: **http://localhost:8000/docs**
- Alternative docs: **http://localhost:8000/redoc**

## Endpoints

### `GET /health`

Check if the server is up and which market areas are available.

```bash
curl "http://localhost:8000/health"
```

Response:

```json
{
  "status": "ok",
  "available_areas": ["America"]
}
```

---

### `GET /api/{area}/{ticker}`

Fetch historical OHLCV bars for a stock.

**Path parameters:**

| Param | Type | Description | Example |
|-------|------|-------------|---------|
| `area` | string | Market area | `America`, `SS`, `SZ` |
| `ticker` | string | Stock ticker | `AAPL`, `600600` |

**Query parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `start_range` | string | no | 5 years ago | Start date `YYYY-MM-DD` |
| `end_range` | string | no | today | End date `YYYY-MM-DD` |

**Example:**

```bash
# Default: 5 years of data
curl "http://localhost:8000/api/America/AAPL"

# Specific date range
curl "http://localhost:8000/api/America/AAPL?start_range=2024-01-01&end_range=2024-12-31"
```

**Response:**

```json
{
  "ticker": "AAPL",
  "area": "America",
  "start_date": "2019-07-20",
  "end_date": "2024-07-19",
  "total_bars": 1258,
  "bars": [
    {
      "date": "2019-07-22",
      "open": 50.80,
      "high": 51.20,
      "low": 50.50,
      "close": 51.10,
      "volume": 23456700
    }
  ]
}
```

**Errors:**

| Code | Meaning |
|------|---------|
| `404` | Ticker not found or no data in range |
| `422` | Invalid date format |

---

### `POST /api/{area}/{ticker}/backtest`

Submit buy-in and sell-out orders as date→quantity (or date→dollars) maps. The server resolves dates to the nearest trading day, executes FIFO-matched round-trips, and returns per-trade detail plus aggregate statistics.

**Request body:**

```json
{
  "start_capital": 100000.00,
  "commission_per_share": 0.005,
  "buy_mode": "shares",
  "buy_in": {
    "2023-01-10": 100,
    "2023-04-15": 50
  },
  "sell_out": {
    "2023-07-20": 150
  }
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `start_capital` | float | no | `100000.00` | Initial cash |
| `commission_per_share` | float | no | `0.005` | Per-share commission |
| `buy_mode` | string | no | `"shares"` | `"shares"` — *buy_in* values are share counts; `"dollars"` — *buy_in* values are dollar amounts |
| `buy_in` | object | yes | — | Map of `"date": quantity_or_dollars` |
| `sell_out` | object | yes | — | Map of `"date": quantity` (always shares) |

**Examples:**

*Shares mode (default):*

```bash
curl -X POST "http://localhost:8000/api/America/AAPL/backtest" \
  -H "Content-Type: application/json" \
  -d '{
    "start_capital": 100000,
    "buy_in": {
      "2023-01-10": 100,
      "2023-04-15": 50
    },
    "sell_out": {
      "2023-07-20": 150
    }
  }'
```

*Dollars mode — values are dollar amounts, converted to integer shares at the open price:*

```bash
curl -X POST "http://localhost:8000/api/America/AAPL/backtest" \
  -H "Content-Type: application/json" \
  -d '{
    "start_capital": 100000,
    "buy_mode": "dollars",
    "buy_in": {
      "2023-01-10": 5000,
      "2023-04-15": 2500
    },
    "sell_out": {
      "2023-07-20": 50
    }
  }'
```

In this example, $5,000 on 2023-01-10 buys ``floor(5000 / open_price)`` shares filled at the open; $2,500 on 2023-04-15 buys ``floor(2500 / open_price)`` more.

**Response:**

```json
{
  "ticker": "AAPL",
  "area": "America",
  "start_capital": 100000.00,
  "final_equity": 108420.00,
  "total_return_pct": 8.42,
  "total_trades": 2,
  "closed_trades": [
    {
      "trade_id": 1,
      "buy_date": "2023-01-10",
      "buy_price": 132.50,
      "quantity": 100,
      "extra_buys": [],
      "total_quantity": 100,
      "avg_entry_price": 132.50,
      "sell_date": "2023-07-20",
      "sell_price": 195.10,
      "gross_pnl": 6260.00,
      "commission_total": 1.00,
      "net_pnl": 6259.00,
      "return_pct": 47.24,
      "days_held": 191,
      "gain_per_day_pct": 0.247
    }
  ],
  "win_rate": 1.0,
  "avg_return_pct": 47.24,
  "avg_days_held": 191.0,
  "avg_gain_per_day_pct": 0.247,
  "total_commission": 1.00,
  "max_drawdown_pct": -3.50
}
```

**Response fields:**

| Field | Description |
|-------|-------------|
| `start_capital` | Initial cash balance |
| `final_equity` | Cash + value of remaining position at the last available date |
| `total_return_pct` | `(final_equity - start_capital) / start_capital × 100` |
| `total_trades` | Number of closed round-trips |
| `closed_trades[]` | Per-trade breakdown (see below) |
| `win_rate` | Fraction of trades with `net_pnl > 0` |
| `avg_return_pct` | Mean return % across all closed trades |
| `avg_days_held` | Mean holding period in calendar days |
| `avg_gain_per_day_pct` | Mean daily return % per trade |
| `total_commission` | Sum of all commissions paid |
| `max_drawdown_pct` | Largest peak-to-trough equity decline |

**Closed trade fields:**

| Field | Description |
|-------|-------------|
| `trade_id` | Sequential trade number |
| `buy_date` / `buy_price` | First buy lot date and price |
| `quantity` | Shares from the first buy lot |
| `extra_buys` | Additional buy lots merged into this trade (empty if single buy) |
| `total_quantity` | Total shares in this round-trip |
| `avg_entry_price` | Weighted average entry price across all lots |
| `sell_date` / `sell_price` | Sell execution date and price |
| `gross_pnl` | `(sell_price - avg_entry) × total_quantity` |
| `commission_total` | Total commission for both buy and sell sides |
| `net_pnl` | `gross_pnl - commission_total` |
| `return_pct` | `net_pnl / entry_value × 100` |
| `days_held` | Calendar days between earliest buy and sell |
| `gain_per_day_pct` | `return_pct / days_held` |

**Execution rules:**

1. **Fill price** — in *shares* mode buys and all sells fill at the bar's `close` price.  In *dollars* mode buys fill at the bar's `open` price.  If the date falls on a weekend/holiday the next available trading day is used.
2. **Dollars → shares** — when `buy_mode` is `"dollars"`, each value is divided by the open price and floored to an integer share count: ``shares = floor(dollars / open_price)``.
3. **FIFO matching** — earliest unsold shares are matched against each sell
4. **Multi-buy consolidation** — when one sell closes shares from multiple buys, the trade includes `extra_buys` and a weighted `avg_entry_price`
5. **Remaining position** — unsold shares at the end are marked to market using the last available close
6. **All events are chronological** — buy_in and sell_out dates are interleaved and processed in date order regardless of JSON key order

**Errors:**

| Code | Meaning |
|------|---------|
| `400` | Insufficient shares, negative quantity, empty maps, date not found |
| `404` | Ticker not found |
| `422` | Malformed JSON or wrong types |

---

## How It Works

```
Client                          Server
  │                               │
  ├─ GET /api/America/AAPL ──────►│  reads stock_data/America/AAPL.txt
  │◄─────── JSON bars ────────────┤  with pandas, returns as JSON
  │                               │
  ├─ POST /api/America/AAPL/backtest ─►│  resolves dates to trading days
  │   {buy_in, sell_out}          │  sorts events chronologically
  │                               │  matches sells vs buys (FIFO)
  │◄─────── stats + trades ───────┤  computes P&L, win rate, drawdown
```

## Order Matching Walkthrough

```
Input:
  buy_in:  {"2021-01-05": 100, "2021-02-10": 200}
  sell_out: {"2021-03-01": 150}

Step 1 — Sort chronologically:
  2021-01-05  BUY   100 @ $50
  2021-02-10  BUY   200 @ $55
  2021-03-01  SELL  150 @ $60

Step 2 — Execute:
  After buys: inventory = [{qty:100, entry:$50}, {qty:200, entry:$55}]
  Sell 150: take 100 from lot 1, 50 from lot 2
    → Trade 1: 150 shares, avg entry ($50×100 + $55×50)/150 = $51.67
    → Net P&L: 150×$60 - $7750 - commission
  Remaining: 150 shares from lot 2 → marked at last close for final_equity
```

## Configuration

All settings live in `backtest_server/config.py` and can be overridden via environment variables:

| Env Variable | Default | Description |
|-------------|---------|-------------|
| `BACKTEST_DATA_DIR` | `../stock_data/` | Path to CSV data directory |
| `BACKTEST_DEFAULT_YEARS` | `5` | Years of data returned when no range specified |
| `BACKTEST_HOST` | `0.0.0.0` | Server bind address |
| `BACKTEST_PORT` | `8000` | Server port |
| `BACKTEST_DEFAULT_CAPITAL` | `100000.00` | Default starting cash |
| `BACKTEST_DEFAULT_COMMISSION` | `0.005` | Default per-share commission |

```bash
# Example: custom port and data directory
BACKTEST_PORT=9000 BACKTEST_DATA_DIR=/data/stocks python -m backtest_server.main
```

## Data Format

The server reads CSV files created by `scrapper.py`:

```
stock_data/{area}/{ticker}.txt    ← e.g. stock_data/America/AAPL.txt
```

Format (no header, QUOTE_NONNUMERIC):

```
"2021-07-19","2.91","2.99","2.65","2.98","650200"
"2021-07-20","3.02","3.30","2.90","3.28","377300"
```

Columns: `Date, Close, High, Low, Open, Volume`

## Package Structure

```
backtest_server/
├── __init__.py
├── main.py        # FastAPI app, routes, error handlers
├── config.py      # Settings (env-variable overridable)
├── models.py      # Pydantic request/response schemas
├── loader.py      # CSV → pandas DataFrame → bar dicts
├── matcher.py     # FIFO buy/sell matching engine
├── stats.py       # Win rate, drawdown, aggregate stats
└── README.md      # This file
```

## Dependencies

- **Python 3.10+**
- **FastAPI** — web framework with auto-validation and OpenAPI docs
- **uvicorn** — ASGI server
- **pandas** — data loading and date handling (already in project)
- **pydantic** — request/response validation (ships with FastAPI)

All are already present in the project's `requirements.txt` or installed alongside FastAPI.
