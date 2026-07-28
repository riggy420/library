# Price Alert Subscriber System — Design Proposal

## Overview

A pub/sub mechanism on top of `ib_insync`:

- **Subscribe** a ticker + condition + callback.
- The system multiplexes all subscriptions into a single market-data stream.
- On each tick, conditions are evaluated; when one fires its callback runs and the
  subscription is consumed (or repeats, depending on mode).
- **Unsubscribe** removes a subscription at any time.

No polling.  No per-ticker connection.  One shared `IB` instance, one event loop.

---

## Concepts

```
┌──────────────────────────────────────────────────────────┐
│                    AlertRegistry                          │
│                                                          │
│  subscriptions: dict[ticker, list[Subscription]]         │
│                                                          │
│  subscribe(ticker, condition, callback) -> sub_id        │
│  unsubscribe(sub_id)                                     │
│  list_all() -> list[Subscription]                        │
│  list_by_ticker(ticker) -> list[Subscription]            │
└─────────────────────┬────────────────────────────────────┘
                      │  owns
┌─────────────────────▼────────────────────────────────────┐
│                   AlertEngine                             │
│                                                          │
│  ib: IB                           # shared connection    │
│  registry: AlertRegistry                                 │
│  tickers: dict[ticker, Ticker]    # ib_insync tickers    │
│                                                          │
│  start()   -> begins the event loop                      │
│  stop()    -> disconnects, clears tickers                │
│  _on_tick(ticker) -> evaluate & fire                     │
└──────────────────────────────────────────────────────────┘
```

---

## Subscription Data Model

```python
@dataclass
class Subscription:
    id: str                          # uuid
    ticker: str                      # e.g. "AAPL"
    condition: AlertCondition        # what triggers it
    action: Callable                 # what happens when it fires
    mode: Literal["once", "every"]   # fire once and auto-unsub, or repeat
    created_at: datetime
    fired_at: datetime | None
    metadata: dict                   # arbitrary user data passed through
```

### AlertCondition

```python
@dataclass
class AlertCondition:
    field: Literal["last", "bid", "ask", "close"]   # which price to watch
    operator: Literal[">", "<", ">=", "<=", "==", "cross"]  # comparison
    threshold: float                                  # trigger value
```

The ``cross`` operator fires when price passes through the threshold from
**either** direction — upward (was below, now >=) or downward (was above,
now <=).  A previous tick seeds the baseline; the first tick never fires.

Examples:

| Description | Condition |
|-------------|-----------|
| AAPL crosses $200 | `AlertCondition("last", "cross", 200.0)` |
| TSLA last crosses $180 | `AlertCondition("last", "cross", 180.0)` |

---

## API Surface

### `subscribe()`

```python
sub_id = engine.subscribe(
    ticker="AAPL",
    condition=AlertCondition("last", "cross", 200.0),
    callback=lambda sub: print(f"🚨 {sub.ticker} crossed {sub.condition.threshold} at ${sub.fire_price:.2f}"),
    mode="once",             # or "every"
    metadata={"strategy": "drop-rebound"},
)
# -> "sub_a1b2c3d4"
```

Returns a subscription ID string.  The `callback` receives the `Subscription` object
(with `fired_at` set and `fire_price` holding the price that triggered the crossing).

### `unsubscribe()`

```python
engine.unsubscribe("sub_a1b2c3d4")
# -> True if removed, False if not found

engine.unsubscribe_all("AAPL")
# -> removes every subscription for that ticker
```

### `list_*()`

```python
engine.list_all()                    # -> list[Subscription]
engine.list_by_ticker("AAPL")        # -> list[Subscription]
engine.list_active()                 # -> only unfired + not cancelled
```

### `start()` / `stop()`

```python
engine.start()    # subscribes to market data for all registered tickers, begins eval
engine.stop()     # unsubscribes from IB market data, clears tickers (registry survives)
```

---

## Lifecycle

```
  subscribe()
      │
      ▼
  ┌─────────┐    start()     ┌──────────┐   tick arrives    ┌───────────┐
  │ PENDING │───────────────►│  ARMED   │──────────────────►│ EVALUATE  │
  └─────────┘                └──────────┘                   └─────┬─────┘
       ▲                         ▲                               │
       │                         │                    ┌──────────┴──────────┐
       │  unsubscribe()          │                    │ condition met?       │
       ▼                         │                    └──────┬──────┬───────┘
  ┌─────────┐                   │                      YES ▼      │ NO
  │ REMOVED │                   │                    ┌──────────┐ │
  └─────────┘                   │                    │  FIRE    │ │ stay
                                │                    │ callback │ │ ARMED
                                │                    └────┬─────┘ │
                                │                         │       │
                                │              mode="once" │       │
                                │          ┌──────────────┘       │
                                │          ▼                      │
                                │   ┌──────────┐                  │
                                │   │  DONE    │    mode="every"  │
                                │   │ (kept in │◄─────────────────┘
                                │   │ history) │   re-arm
                                │   └──────────┘
                                │
                                │   stop() or disconnect
                                │          ▼
                                │   ┌──────────┐
                                └───│  ARMED   │  (registry survives; re-startable)
                                    └──────────┘
```

- **PENDING** — subscribed but engine not yet started (or stopped).
- **ARMED** — engine running, market data streaming, waiting for price.
- **EVALUATE** — tick arrived; checking condition.
- **FIRE** — condition met; callback executed.
- **DONE** — `mode="once"` terminal state.  Stays in registry for audit.
- **REMOVED** — explicitly unsubscribed.  Removed from registry.

---

## Integration with the existing `ib_paper` package

```
ib_paper/
├── connection.py      # ConnectionManager  (already exists)
├── alerts.py          # NEW — AlertEngine, AlertRegistry, Subscription, AlertCondition
├── account.py         # (existing)
├── orders.py          # (existing — Alert callback can call OrderService)
├── positions.py       # (existing)
├── types.py           # (existing — add AlertCondition, Subscription types here)
├── cli.py             # (existing — add `ibpaper alert` commands)
└── docs/
    └── alert-subscriber-design.md   # this file
```

### CLI sketch

```bash
# Subscribe to a price-crossing alert
ibpaper alert subscribe AAPL --cross 200.0

# Subscribe with a repeat (re-arms after every fire)
ibpaper alert subscribe AAPL --cross 200.0 --every

# List active subscriptions
ibpaper alert list

# Unsubscribe
ibpaper alert unsubscribe <sub_id>

# Start the alert engine (foreground, streaming)
ibpaper alert watch
```

### Callback → order example

The callback can call directly into the existing `OrderService`:

```python
from ib_paper.orders import OrderService
from ib_paper.types import OrderRequest, OrderAction, OrderType

def sell_on_cross(sub: Subscription) -> None:
    """When AAPL crosses below $180, sell 100 shares."""
    request = OrderRequest(
        symbol=sub.ticker,
        action=OrderAction.SELL,
        total_quantity=100,
        order_type=OrderType.MKT,
    )
    trade = OrderService.place_order(sub.metadata["ib"], request)
    print(f"✓ Stop-loss executed at ${sub.fire_price:.2f}: {trade}")

engine.subscribe(
    ticker="AAPL",
    condition=AlertCondition("last", "cross", 180.0),
    callback=sell_on_cross,
    mode="once",
    metadata={"ib": ib},   # pass the IB handle through
)
```

---

## Threading & Execution model

The `AlertEngine` runs on a single thread using `ib_insync`'s built-in event loop
(`ib.run()` is blocking).  Subscriptions can be added/removed from another thread
via a thread-safe queue:

```
Main thread                           Alert-engine thread
──────────                            ───────────────────
subscribe("AAPL", ...)
  │  puts (ADD, sub) on queue ──────►  _process_queue()
  │                                    adds sub to registry
  │                                    ib.reqMktData(AAPL) if first sub for AAPL
  ◄──────────────────────────────────  returns sub_id

unsubscribe(id)
  │  puts (REMOVE, id) on queue ───►  _process_queue()
  │                                    removes sub from registry
  │                                    ib.cancelMktData(AAPL) if last sub for AAPL
```

The queue is drained at the start of each tick cycle so adds/removes are
visible within one tick at most.

---

## What this enables in the broader project

Once the alert engine is in place, the `random_algorithm.py` backtest results
could feed directly into live alerts:

```
backtest finds top ticker  →  subscribe to that ticker  →  alert fires  →  auto-place order
```

Or the other direction — alerts trigger logging that feeds back into the
backtest for walk-forward validation.

---

## Summary

| Feature | How |
|---------|-----|
| Subscribe | `engine.subscribe(ticker, condition, callback, mode)` |
| Unsubscribe | `engine.unsubscribe(id)` or `engine.unsubscribe_all(ticker)` |
| Multiple tickers | One shared `ib_insync` connection, ticker→subscriptions map |
| Callback on fire | User-provided `Callable[[Subscription], None]` |
| Fire once | `mode="once"` — auto-unsubscribes after callback |
| Fire every time | `mode="every"` — re-arms after callback |
| Thread safety | Internal queue for cross-thread subscribe/unsubscribe |
| Persistence | Optional: serialize `list_all()` to JSON, reload on restart |
| CLI | `ibpaper alert subscribe/list/unsubscribe/watch` |
