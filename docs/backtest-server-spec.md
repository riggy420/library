# Backtest Backend Server — Specification

## 1. Overview

A lightweight **FastAPI** server with exactly two endpoints:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/{area}/{ticker}` | Fetch historical OHLCV bars (default: 5 years) |
| `POST` | `/api/{area}/{ticker}/backtest` | Submit buy/sell orders, receive performance metrics |

No sessions. No state. Each POST is a self-contained batch backtest.

---

## 2. GET — Fetch Stock Data

### `GET /api/{area}/{ticker}`

Returns historical OHLCV data from the existing `stock_data/{area}/{ticker}.txt` CSV files.

#### Path Parameters

| Param | Type | Description | Example |
|-------|------|-------------|---------|
| `area` | string | Market area | `America`, `SS`, `SZ` |
| `ticker` | string | Stock ticker symbol | `AAPL`, `600600` |

#### Query Parameters

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `start_range` | string | no | 5 years ago | Start date `YYYY-MM-DD` |
| `end_range` | string | no | today | End date `YYYY-MM-DD` |

#### Response `200 OK`

```json
{
  "ticker": "AAPL",
  "area": "America",
  "start_date": "2019-07-19",
  "end_date": "2024-07-19",
  "total_bars": 1258,
  "bars": [
    {
      "date": "2019-07-19",
      "open": 50.80,
      "high": 51.20,
      "low": 50.50,
      "close": 51.10,
      "volume": 23456700
    }
  ]
}
```

> **Note:** `bars` is the full array. For a 5-year daily stock, this is ~1,258 entries — well within acceptable JSON payload size.

#### Error Responses

| Code | Body |
|------|------|
| `404` | `{"error": "Ticker not found", "ticker": "XYZ", "area": "America"}` |
| `404` | `{"error": "No data in range", "ticker": "AAPL", "start_range": "2030-01-01", "end_range": "2030-12-31"}` |
| `422` | `{"error": "Invalid date format", "detail": "start_range must be YYYY-MM-DD"}` |

---

## 3. POST — Run Backtest

### `POST /api/{area}/{ticker}/backtest`

Submit a batch of buy-in and sell-out orders. The server matches them, simulates execution against historical prices, and returns performance statistics.

#### Request Body

```json
{
  "start_capital": 100000.00,
  "commission_per_share": 0.005,
  "buy_in": {
    "2021-07-19": 100,
    "2021-08-15": 50,
    "2022-01-10": 200
  },
  "sell_out": {
    "2021-09-01": 150,
    "2022-03-20": 200
  }
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `start_capital` | float | no | `100000.00` | Initial cash |
| `commission_per_share` | float | no | `0.005` | Per-share commission cost |
| `buy_in` | object | yes | — | Map of `"date": quantity` |
| `sell_out` | object | yes | — | Map of `"date": quantity` |

#### Execution Rules

1. **Fill price** = `close` price on that date. If the date falls on a weekend/holiday (no bar), the **next available trading day** is used. If no subsequent bar exists → error.
2. **Buy-in** deducts `quantity × close + (quantity × commission_per_share)` from cash, adds shares to position.
3. **Sell-out** adds `quantity × close - (quantity × commission_per_share)` to cash, removes shares from position.
4. **Matching**: FIFO — earliest unsold shares are matched against the next sell. Each matched round-trip produces one **closed trade**.
5. **Constraint**: Cannot sell more shares than currently held. If `sell_out` quantity exceeds position at that date → error.
6. **Ordering**: All events (buys and sells) are processed in chronological order by date, regardless of how they appear in the JSON.

#### Response `200 OK`

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
      "buy_date": "2021-07-19",
      "buy_price": 146.80,
      "quantity": 100,
      "sell_date": "2021-09-01",
      "sell_price": 152.30,
      "gross_pnl": 550.00,
      "commission_total": 1.00,
      "net_pnl": 549.00,
      "return_pct": 3.74,
      "days_held": 44,
      "gain_per_day_pct": 0.085
    },
    {
      "trade_id": 2,
      "buy_date": "2021-08-15",
      "buy_price": 149.10,
      "quantity": 50,
      "buy_date_2": "2022-01-10",
      "buy_price_2": 165.00,
      "quantity_2": 200,
      "total_quantity": 250,
      "avg_entry_price": 161.82,
      "sell_date": "2022-03-20",
      "sell_price": 170.50,
      "gross_pnl": 2170.00,
      "commission_total": 2.50,
      "net_pnl": 2167.50,
      "return_pct": 5.36,
      "days_held": 69,
      "gain_per_day_pct": 0.078
    }
  ],
  "win_rate": 1.0,
  "avg_return_pct": 4.55,
  "avg_days_held": 56.5,
  "avg_gain_per_day_pct": 0.081,
  "total_commission": 3.50,
  "max_drawdown_pct": -2.10
}
```

| Field | Type | Description |
|-------|------|-------------|
| `start_capital` | float | Initial cash |
| `final_equity` | float | Cash + value of any remaining position at last data date |
| `total_return_pct` | float | `(final_equity - start_capital) / start_capital × 100` |
| `total_trades` | int | Number of closed round-trips |
| `closed_trades[]` | array | Detailed breakdown of each matched buy→sell |
| `win_rate` | float | Fraction of trades with `net_pnl > 0` |
| `avg_return_pct` | float | Mean `return_pct` across closed trades |
| `avg_days_held` | float | Mean holding period in calendar days |
| `avg_gain_per_day_pct` | float | Mean of each trade's `net_pnl / (entry_value × days_held) × 100` |
| `total_commission` | float | Sum of all commission paid |
| `max_drawdown_pct` | float | Worst peak-to-trough equity decline during the period |

#### Closed Trade Fields (multi-buy handling)

When a single sell closes shares accumulated across **multiple buy-ins**, the trade shows:

- **First buy** as the primary (`buy_date`, `buy_price`, `quantity`)
- **Subsequent buys** as `buy_date_N`, `buy_price_N`, `quantity_N` appended
- **`avg_entry_price`** = weighted average of all entry prices
- **`days_held`** = sell date minus **earliest** buy date in the batch

The frontend can use `avg_entry_price` and `total_quantity` as the canonical summary.

#### Partial Sell Matching Example

```
Buy 2021-01-05: 100 shares @ $50
Buy 2021-02-10: 200 shares @ $55
Sell 2021-03-01: 150 shares @ $60

→ Trade 1: 100 shares from first buy, avg entry $50, net P&L on those 100 shares
  Remaining: 50 shares sold from second buy
→ Trade 2: 50 shares from second buy, avg entry $55, net P&L
  Remaining position: 150 shares from second buy still open (valued at last close for final_equity)
```

#### Error Responses

| Code | Body |
|------|------|
| `400` | `{"error": "Insufficient shares", "detail": "Sell on 2022-03-20 for 200 shares but only 150 held"}` |
| `400` | `{"error": "Date not found", "detail": "No trading data on or after 2025-12-25"}` |
| `400` | `{"error": "buy_in and sell_out cannot both be empty"}` |
| `400` | `{"error": "Negative quantity", "detail": "buy_in on 2021-07-19 has quantity -10"}` |
| `422` | Pydantic validation error (malformed JSON, wrong types) |

---

## 4. Architecture

```
┌──────────────────────────────────────────┐
│              Client (anything)            │
└──────────────────┬───────────────────────┘
                   │ HTTP
┌──────────────────▼───────────────────────┐
│         FastAPI Backtest Server           │
│                                           │
│  GET /api/{area}/{ticker}                 │
│    └─ CSV Loader → pandas → JSON          │
│                                           │
│  POST /api/{area}/{ticker}/backtest       │
│    └─ Order Matcher (FIFO)               │
│       └─ P&L Calculator                   │
│          └─ Stats Aggregator              │
│                                           │
│         stock_data/{area}/{ticker}.txt    │
└──────────────────────────────────────────┘
```

### 4.1 Tech Stack

| Layer | Choice |
|-------|--------|
| Framework | **FastAPI** (async, Pydantic validation, auto OpenAPI docs at `/docs`) |
| Data | **pandas** (already in project, natural for OHLCV) |
| Date handling | **pandas date_range + bfill** for non-trading-day resolution |
| Validation | **Pydantic v2** models for request/response |

### 4.2 File Structure

```
library/
├── backtest_server/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, route registration
│   ├── config.py               # DATA_DIR, defaults
│   ├── models.py               # Pydantic request/response schemas
│   ├── loader.py               # CSV → pandas DataFrame → Bar dicts
│   ├── matcher.py              # FIFO buy/sell matching engine
│   └── stats.py                # Win rate, avg gain/day, drawdown
```

### 4.3 Key Logic: Date Resolution

When a buy/sell date doesn't land on a trading day:

```python
def resolve_date(df: pd.DataFrame, target_date: str) -> pd.Timestamp:
    """Find the next available trading day at or after target_date."""
    date = pd.Timestamp(target_date)
    available = df[df.index >= date]
    if available.empty:
        raise ValueError(f"No trading data on or after {target_date}")
    return available.index[0]
```

### 4.4 Key Logic: FIFO Matching

```python
def match_orders(buys: list, sells: list, bars: dict) -> list[ClosedTrade]:
    """
    Sort all events chronologically.
    Maintain a FIFO queue of (buy_date, price, remaining_qty).
    On each sell, pop from queue front until sell qty is exhausted.
    Each pop produces one ClosedTrade row.
    """
```

---

## 5. Quick Example

```bash
# 1. Check available data range
curl "http://localhost:8000/api/America/AAPL"

# Response condensed: 5 years of daily bars, ~1258 entries

# 2. Run a backtest
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

# Response:
# {
#   "total_trades": 1,
#   "win_rate": 1.0,
#   "avg_gain_per_day_pct": 0.092,
#   ...
# }
```

---

## 6. Configuration

`backtest_server/config.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIR` | `../stock_data/` | Path to CSV directory (relative to server) |
| `DEFAULT_YEARS` | `5` | Years of data returned when no range given |
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | Server port |
| `DEFAULT_CAPITAL` | `100000.0` | Default start capital |
| `DEFAULT_COMMISSION` | `0.005` | Per-share commission |

---

## 7. Deferred to v2

- Short selling (sell before buy)
- Multiple tickers in one backtest
- WebSocket streaming
- Persistent storage of results
- Strategy classes / pluggable logic
