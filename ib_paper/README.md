# ibpaper — Interactive Brokers Paper Trading CLI

Trade your IB paper account from the command line, or via a REST + WebSocket API server.

## Prerequisites

- **Python 3.10+**
- **TWS** (Trader Workstation) or **IB Gateway** running with API enabled
  - *File → Global Configuration → API → Settings → Enable ActiveX and Socket Clients*
  - Paper trading uses port **7497** by default

## Installation

```powershell
# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install ibpaper in editable mode
pip install -e .
```

## Quick Start

```bash
# 1. Check your config (defaults are fine for local TWS paper)
ibpaper setup --show

# 2. View your paper account balance
ibpaper account

# 3. Enter a position
ibpaper buy AAPL --qty 10

# 4. Check your positions
ibpaper positions

# 5. Exit a position
ibpaper sell AAPL --all

# 6. Start the REST + WebSocket server
ibpaper-server
```

---

## CLI Reference (`ibpaper`)

### `ibpaper setup`

Configure connection settings (saved to `~/.ib_paper/config.json`).

```bash
ibpaper setup --show               # View current config
ibpaper setup --port 7497          # Set paper trading port
ibpaper setup --default-qty 50     # Change default order quantity
```

### `ibpaper account`

View account information.

```bash
ibpaper account                    # Summary (default)
ibpaper account --portfolio        # Positions + P&L
ibpaper account --pnl              # P&L breakdown only
```

### `ibpaper buy SYMBOL`

Enter a position.

```bash
ibpaper buy AAPL                   # Market buy, default quantity
ibpaper buy AAPL --qty 50          # Market buy 50 shares
ibpaper buy AAPL -q 10 -l 150.00   # Limit buy @ $150
ibpaper buy AAPL --stop 155.00     # Stop buy @ $155
ibpaper buy AAPL --dry-run         # Validate without placing
ibpaper buy AAPL --qty 10 --yes    # Skip confirmation prompt
```

### `ibpaper sell SYMBOL`

Exit a position.

```bash
ibpaper sell AAPL --all            # Close entire position at market
ibpaper sell AAPL --qty 50         # Sell 50 shares at market
ibpaper sell AAPL -q 10 -l 155.00  # Limit sell @ $155
ibpaper sell AAPL --all --stop 145 # Stop-loss on full position
ibpaper sell AAPL --dry-run        # Validate without placing
```

### `ibpaper positions`

List current positions.

```bash
ibpaper positions                  # All positions
ibpaper positions --symbol AAPL    # Single position detail
```

### `ibpaper orders`

View orders from the current session.

```bash
ibpaper orders                     # Active orders
ibpaper orders --completed         # Filled / cancelled
ibpaper orders --all               # Everything
```

### `ibpaper cancel ID`

Cancel a pending order.

```bash
ibpaper cancel 42
```

---

## Server Reference (`ibpaper-server`)

The server listens on **port 8081** by default and provides both a REST API
and a WebSocket interface for real-time streaming.

### Starting the server

```bash
ibpaper-server                     # Start on 0.0.0.0:8081
ibpaper-server --port 8082         # Custom port
ibpaper-server --host 127.0.0.1    # Local only
ibpaper-server -h                  # Full help with all endpoints
```

### REST API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Full API documentation (JSON) |
| `GET` | `/health` | Server + IB connection status |
| `GET` | `/account` | Account summary (NetLiq, Cash, BuyingPower, P&L) |
| `GET` | `/positions` | All open positions |
| `GET` | `/positions/{TICKER}` | Single position detail |
| `GET` | `/orders` | All orders from this session |
| `POST` | `/buy/{TICKER}` | Place a buy order |
| `POST` | `/sell/{TICKER}` | Place a sell order |

### REST examples

> **Windows users:** the curl examples below work in **Git Bash** (comes with
> Git for Windows) or **WSL**.  For PowerShell, see the [PowerShell
> examples](#powershell-examples) section.

**Single-line curl (Git Bash / WSL / macOS / Linux):**

```bash
# Health check
curl http://localhost:8081/health

# Account summary
curl http://localhost:8081/account

# Market buy — 1 share AAPL
curl -X POST http://localhost:8081/buy/AAPL -H "Content-Type: application/json" -d "{\"market\":\"\",\"qty\":1}"

# Limit buy — 10 shares @ $150
curl -X POST http://localhost:8081/buy/AAPL -H "Content-Type: application/json" -d "{\"limit\":\"150.00\",\"qty\":10}"

# Stop buy — 25 shares @ $155
curl -X POST http://localhost:8081/buy/AAPL -H "Content-Type: application/json" -d "{\"stop\":\"155.00\",\"qty\":25}"

# Market sell — close entire position
curl -X POST http://localhost:8081/sell/AAPL -H "Content-Type: application/json" -d "{\"market\":\"\",\"all\":true}"

# Limit sell — 10 shares @ $155
curl -X POST http://localhost:8081/sell/AAPL -H "Content-Type: application/json" -d "{\"limit\":\"155.00\",\"qty\":10}"

# Stop-loss — entire position @ $140
curl -X POST http://localhost:8081/sell/AAPL -H "Content-Type: application/json" -d "{\"stop\":\"140.00\",\"all\":true}"

# View positions
curl http://localhost:8081/positions

# View orders
curl http://localhost:8081/orders
```

**Example responses:**

```json
{"server":"running","ib_connected":true,"websocket_clients":0}

{"net_liquidation":1000040.87,"buying_power":6525960.05}

{"order_id":4,"action":"BUY","order_type":"MKT","quantity":1,"status":"PreSubmitted"}

{"order_id":6,"action":"BUY","order_type":"LMT","limit_price":150.00,"quantity":10,"status":"PreSubmitted"}
```

### PowerShell examples

PowerShell's `Invoke-RestMethod` is a native alternative to curl:

```powershell
# Health check
Invoke-RestMethod http://localhost:8081/health

# Account summary
Invoke-RestMethod http://localhost:8081/account

# Market buy — 1 share AAPL
Invoke-RestMethod -Uri http://localhost:8081/buy/AAPL -Method Post `
  -ContentType "application/json" `
  -Body '{"market":"","qty":1}'

# Limit buy — 10 shares @ $150
Invoke-RestMethod -Uri http://localhost:8081/buy/AAPL -Method Post `
  -ContentType "application/json" `
  -Body '{"limit":"150.00","qty":10}'

# Stop buy — 25 shares @ $155
Invoke-RestMethod -Uri http://localhost:8081/buy/AAPL -Method Post `
  -ContentType "application/json" `
  -Body '{"stop":"155.00","qty":25}'

# Market sell — close entire position
Invoke-RestMethod -Uri http://localhost:8081/sell/AAPL -Method Post `
  -ContentType "application/json" `
  -Body '{"market":"","all":true}'

# Limit sell — 10 shares @ $155
Invoke-RestMethod -Uri http://localhost:8081/sell/AAPL -Method Post `
  -ContentType "application/json" `
  -Body '{"limit":"155.00","qty":10}'

# Stop-loss — entire position @ $140
Invoke-RestMethod -Uri http://localhost:8081/sell/AAPL -Method Post `
  -ContentType "application/json" `
  -Body '{"stop":"140.00","all":true}'

# View positions
Invoke-RestMethod http://localhost:8081/positions

# View orders
Invoke-RestMethod http://localhost:8081/orders
```

### CMD examples (Command Prompt)

Use double quotes with escaped inner quotes:

```cmd
REM Health check
curl http://localhost:8081/health

REM Market buy — 1 share AAPL
curl -X POST http://localhost:8081/buy/AAPL -H "Content-Type: application/json" -d "{\"market\":\"\",\"qty\":1}"

REM Limit buy — 10 shares @ $150
curl -X POST http://localhost:8081/buy/AAPL -H "Content-Type: application/json" -d "{\"limit\":\"150.00\",\"qty\":10}"

REM Market sell — close entire position
curl -X POST http://localhost:8081/sell/AAPL -H "Content-Type: application/json" -d "{\"market\":\"\",\"all\":true}"
```

### Request body formats

| JSON | Behaviour |
|------|-----------|
| `{"market":""}` | Market order, default quantity |
| `{"market":"","qty":50}` | Market order, 50 shares |
| `{"limit":"150.00"}` | Limit order at $150, default qty |
| `{"limit":"150.00","qty":10}` | Limit order, 10 shares @ $150 |
| `{"stop":"145.00"}` | Stop order at $145, default qty |
| `{"stop":"145.00","qty":25}` | Stop order, 25 shares @ $145 |
| `{"market":"","all":true}` | **Sell only** — close entire position |

Prices accept both strings (`"150.00"`) and numbers (`150.00`).
The `"all"` field accepts `true`, `"true"`, `"yes"`, or `1`.

### Error responses

```bash
# Missing body → 400
curl -X POST http://localhost:8081/buy/AAPL -H "Content-Type: application/json" -d "{}"
# → {"error":"Request body must contain one of: 'market', 'limit', or 'stop'."}

# TWS not running → 503
curl http://localhost:8081/account
# → {"error":"Could not connect to TWS/IB Gateway at 127.0.0.1:7497..."}

# Unknown route → 404 (returns available endpoints)
curl http://localhost:8081/whatever
# → {"error":"Not found. See available endpoints below.","rest_endpoints":{...}}
```

### WebSocket events

Connect to `ws://localhost:8081` and send/receive these events:

**Client → Server:**

| Event | Payload | Purpose |
|-------|---------|---------|
| `subscribe_price` | `{"ticker":"AAPL"}` | Start real-time quotes |
| `unsubscribe_price` | `{"ticker":"AAPL"}` | Stop quotes |
| `subscribe_orders` | `{}` | Live order status pushes |
| `subscribe_positions` | `{}` | Live position P&L pushes |

**Server → Client pushes:**

| Event | Payload |
|-------|---------|
| `price_update` | `{ticker, bid, ask, last, close, high, low, volume, time}` |
| `order_update` | `{order_id, symbol, action, qty, type, status, filled, remaining}` |
| `position_update` | `{symbol, qty, avg_cost, mkt_price, mkt_value, unreal_pnl, pnl_pct}` |

### WebSocket example (wscat — any platform)

```bash
npm install -g wscat
wscat -c ws://localhost:8081
```

Type these JSON messages one at a time:
```
subscribe_price {"ticker":"AAPL"}
subscribe_orders {}
subscribe_positions {}
```

You'll receive a stream of `price_update`, `order_update`, and
`position_update` events.

### WebSocket example (Python)

```python
import socketio

sio = socketio.Client()

@sio.on("connect")
def on_connect():
    print("Connected to ibpaper server")

@sio.on("price_update")
def on_price(data):
    print(f"{data['ticker']}: bid={data['bid']}  ask={data['ask']}  last={data['last']}")

@sio.on("order_update")
def on_order(data):
    print(f"Order {data['order_id']}: {data['symbol']} {data['action']} — {data['status']}")

@sio.on("position_update")
def on_position(data):
    print(f"Position {data['symbol']}: {data['quantity']} @ {data['market_price']}  P&L={data['unrealized_pnl']}")

sio.connect("http://localhost:8081")
sio.emit("subscribe_price", {"ticker": "AAPL"})
sio.emit("subscribe_orders")
sio.emit("subscribe_positions")

# Keep running to receive live updates
import time
time.sleep(60)
```

### Client ID auto-healing

If TWS already has client ID 1 in use (e.g., from another application or a
previous session), the server automatically increments the client ID until it
finds a free one.  The working ID is persisted to config so subsequent starts
use it directly.

---

## Configuration

Config is stored as JSON at `~/.ib_paper/config.json`:

```json
{
  "connection": {
    "host": "127.0.0.1",
    "port": 7497,
    "client_id": 1,
    "timeout": 5
  },
  "defaults": {
    "order_quantity": 100,
    "order_type": "MKT",
    "currency": "USD",
    "exchange": "SMART"
  },
  "safety": {
    "confirm_live": true,
    "confirm_orders": true
  }
}
```

---

## Safety

- **Default port is 7497** (paper). Port 7496 (live) triggers a warning.
- **Confirmation prompt** before every CLI order (skip with `--yes`).
- **`--dry-run`** validates the symbol and order without placing it.
- Server **auto-increments client ID** on collision — no manual port hunting.
- Set `"confirm_live": false` in config to suppress the live-port warning (use with caution).

---

## Programmatic API

```python
from ib_paper import ConnectionManager, AccountService, OrderService

with ConnectionManager() as cm:
    # Account
    snap = AccountService.get_summary(cm.ib)
    print(f"NetLiq: {snap.net_liquidation}")

    # Enter a position
    from ib_paper import OrderRequest, OrderAction, OrderType
    req = OrderRequest(symbol="AAPL", action=OrderAction.BUY,
                       total_quantity=10, order_type=OrderType.MKT)
    trade = OrderService.place_order(cm.ib, req)
    print(f"Order {trade.order.orderId}: {trade.orderStatus.status}")
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Could not connect" | Make sure TWS/IB Gateway is running and API is enabled |
| "Symbol could not be resolved" | Check the ticker spelling; try with `--dry-run` first |
| "Order rejected" | Check buying power, order quantity, and price |
| "Client id is already in use" | The server auto-increments; CLI users can run `ibpaper setup --client-id 5` |
| WebSocket connection refused | Ensure `flask-socketio` and `eventlet` are installed: `pip install flask-socketio eventlet` |

## License

MIT
