"""Price-alert subscriber system.

One shared ``ib_insync.IB`` connection multiplexes market-data subscriptions
for all watched tickers.  On each tick, conditions are evaluated; when a
condition fires the user-provided callback runs and the subscription is
consumed (``mode=ONCE``) or re-armed (``mode=EVERY``).

Typical usage::

    from ib_paper import ConnectionManager, AlertEngine, AlertCondition
    from ib_paper.types import AlertField, AlertOperator, AlertMode

    cm = ConnectionManager()
    cm.connect()
    engine = AlertEngine(cm.ib)

    def on_alert(sub):
        print(f"ALERT: {sub.ticker} {sub.condition.describe()}"
              f" -- fired at ${sub.fire_price:.2f}")

    sub_id = engine.subscribe(
        ticker="AAPL",
        condition=AlertCondition(AlertField.LAST, AlertOperator.GTE, 200.0),
        callback=on_alert,
        mode=AlertMode.ONCE,
    )

    engine.run()   # blocks; Ctrl-C to stop
"""

from __future__ import annotations

import queue
import threading
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from ib_insync import IB, Stock, Ticker

from .exceptions import IBPaperError
from .types import (
    AlertCondition,
    AlertField,
    AlertMode,
    AlertOperator,
    Subscription,
)


# ── Exceptions ────────────────────────────────────────────────────────────

class AlertError(IBPaperError):
    """Base for alert-related errors."""


class AlertExistsError(AlertError):
    """A duplicate subscription was rejected."""


class AlertNotRunningError(AlertError):
    """Operation requires the engine to be running."""


# ── Registry ──────────────────────────────────────────────────────────────

class AlertRegistry:
    """Thread-safe container for :class:`Subscription` objects.

    Organised as ``ticker -> list[Subscription]`` for fast lookup during
    tick evaluation.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_ticker: Dict[str, List[Subscription]] = defaultdict(list)
        self._by_id: Dict[str, Subscription] = {}

    # -- write --------------------------------------------------------------

    def add(self, sub: Subscription) -> None:
        with self._lock:
            self._by_ticker[sub.ticker.upper()].append(sub)
            self._by_id[sub.id] = sub

    def remove(self, sub_id: str) -> bool:
        """Remove by ID.  Returns ``True`` if something was removed."""
        with self._lock:
            sub = self._by_id.pop(sub_id, None)
            if sub is None:
                return False
            ticker = sub.ticker.upper()
            lst = self._by_ticker.get(ticker, [])
            if sub in lst:
                lst.remove(sub)
            if not lst:
                self._by_ticker.pop(ticker, None)
            return True

    def remove_all_for(self, ticker: str) -> int:
        """Remove every subscription for *ticker*.  Returns count removed."""
        ticker = ticker.upper()
        with self._lock:
            lst = self._by_ticker.pop(ticker, [])
            count = len(lst)
            for sub in lst:
                self._by_id.pop(sub.id, None)
            return count

    def mark_fired(self, sub: Subscription, price: float) -> None:
        """Stamp a subscription as fired."""
        with self._lock:
            sub.fired_at = datetime.now(timezone.utc).isoformat()
            sub.fire_price = price
            if sub.mode == AlertMode.ONCE:
                self._by_id.pop(sub.id, None)
                ticker = sub.ticker.upper()
                lst = self._by_ticker.get(ticker, [])
                if sub in lst:
                    lst.remove(sub)
                if not lst:
                    self._by_ticker.pop(ticker, None)

    # -- read ---------------------------------------------------------------

    def get(self, sub_id: str) -> Optional[Subscription]:
        with self._lock:
            return self._by_id.get(sub_id)

    def for_ticker(self, ticker: str) -> List[Subscription]:
        with self._lock:
            return list(self._by_ticker.get(ticker.upper(), []))

    def all_tickers(self) -> List[str]:
        with self._lock:
            return sorted(self._by_ticker.keys())

    def list_all(self) -> List[Subscription]:
        with self._lock:
            return list(self._by_id.values())

    def list_active(self) -> List[Subscription]:
        """Subscriptions that haven't fired yet (ONCE) or are repeating (EVERY)."""
        with self._lock:
            return [s for s in self._by_id.values() if s.fired_at is None]

    def ticker_count(self, ticker: str) -> int:
        with self._lock:
            return len(self._by_ticker.get(ticker.upper(), []))

    def total_count(self) -> int:
        with self._lock:
            return len(self._by_id)


# ── Engine ────────────────────────────────────────────────────────────────

class AlertEngine:
    """Evaluates price-alert subscriptions against a live market-data stream.

    Args:
        ib: A **connected** ``ib_insync.IB`` instance.
    """

    def __init__(self, ib: IB) -> None:
        if not ib.isConnected():
            raise AlertError("IB instance must be connected before creating AlertEngine.")
        self._ib = ib
        self.registry = AlertRegistry()
        self._tickers: Dict[str, Ticker] = {}       # ticker -> ib_insync Ticker
        self._callbacks: Dict[str, Callable] = {}    # sub_id -> callback
        self._previous_prices: Dict[str, float] = {} # sub_id -> last known price (for CROSS)
        self._command_queue: queue.Queue = queue.Queue()
        self._running = False
        self._lock = threading.Lock()

    # -- properties ---------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._running

    # -- subscribe / unsubscribe -------------------------------------------

    def subscribe(
        self,
        ticker: str,
        condition: AlertCondition,
        callback: Callable[[Subscription], None],
        mode: AlertMode = AlertMode.ONCE,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Register a new alert subscription.

        Args:
            ticker: Stock symbol (e.g. ``"AAPL"``).
            condition: An :class:`AlertCondition` describing the trigger.
            callback: Called with the :class:`Subscription` when the alert fires.
            mode: :attr:`AlertMode.ONCE` (auto-remove after fire) or
                  :attr:`AlertMode.EVERY` (re-arm after fire).
            metadata: Optional user data attached to the subscription.

        Returns:
            The subscription ID (a UUID string).  Use this to unsubscribe later.
        """
        sub_id = uuid.uuid4().hex[:12]
        sub = Subscription(
            id=sub_id,
            ticker=ticker.upper(),
            condition=condition,
            mode=mode,
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        )

        self.registry.add(sub)
        self._callbacks[sub_id] = callback

        # If the engine is already running, subscribe to market data now.
        # Otherwise it will be picked up on next start().
        if self._running:
            self._command_queue.put(("ADD", sub_id))
        else:
            self._ensure_ticker_subscribed(ticker)

        return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
        """Remove a subscription by ID.  Returns ``True`` if it existed."""
        sub = self.registry.get(sub_id)
        if sub is None:
            return False

        ticker = sub.ticker
        self._callbacks.pop(sub_id, None)
        removed = self.registry.remove(sub_id)

        if removed and self._running:
            self._command_queue.put(("REMOVE", ticker))

        return removed

    def unsubscribe_all(self, ticker: str) -> int:
        """Remove all subscriptions for *ticker*.  Returns count removed."""
        count = self.registry.remove_all_for(ticker)
        if count > 0 and self._running:
            # If no more subs for this ticker, cancel market data
            if self.registry.ticker_count(ticker) == 0:
                self._cancel_ticker(ticker)
        return count

    # -- lifecycle ----------------------------------------------------------

    def run(self) -> None:
        """Start the alert evaluation loop.  **Blocks** until :meth:`stop` is
        called or the IB connection drops.

        Call this after subscribing to all desired alerts.  Use Ctrl-C to
        interrupt.
        """
        if not self._ib.isConnected():
            raise AlertError("IB connection lost. Cannot start alert engine.")

        self._running = True

        # Subscribe to market data for every ticker already in the registry
        for ticker in self.registry.all_tickers():
            self._ensure_ticker_subscribed(ticker)

        # Register a periodic timer to drain the command queue
        self._ib.run()

    def stop(self) -> None:
        """Stop the evaluation loop and cancel all market-data subscriptions.

        The registry survives — call :meth:`run` again to restart.
        """
        self._running = False
        for ticker in list(self._tickers.keys()):
            self._cancel_ticker(ticker)
        try:
            self._ib.disconnect()
        except Exception:
            pass

    # -- internal -----------------------------------------------------------

    def _ensure_ticker_subscribed(self, ticker: str) -> None:
        """Subscribe to market data for *ticker* if not already streaming."""
        ticker = ticker.upper()
        if ticker in self._tickers:
            return

        contract = Stock(ticker, "SMART", "USD")
        try:
            qualified = self._ib.qualifyContracts(contract)
        except Exception:
            return  # ticker not found; subscriptions for it will never fire

        if not qualified:
            return

        tk = self._ib.reqMktData(qualified[0], snapshot=False)
        self._tickers[ticker] = tk
        tk.updateEvent += self._on_tick

    def _cancel_ticker(self, ticker: str) -> None:
        """Cancel market data for *ticker*."""
        ticker = ticker.upper()
        tk = self._tickers.pop(ticker, None)
        if tk is not None:
            tk.updateEvent -= self._on_tick
            try:
                self._ib.cancelMktData(tk.contract)
            except Exception:
                pass

    def _on_tick(self, ticker: Ticker) -> None:
        """Called by ib_insync on every market-data update for any watched ticker."""
        symbol = ticker.contract.symbol.upper()

        # 1. Early exit if no one is watching this ticker
        pending_count = self.registry.ticker_count(symbol)
        if pending_count == 0:
            return

        # 2. Process command queue (cross-thread subscribe/unsubscribe)
        self._drain_queue()

        # 3. Re-check count — drain may have removed the last subscription
        subs = self.registry.for_ticker(symbol)
        if not subs:
            return

        for sub in subs:
            # Guard: subscription may have been removed by an earlier
            # iteration's mark_fired while we're still looping
            if self.registry.get(sub.id) is None:
                continue

            price = self._extract_price(ticker, sub.condition.field)
            if price is None or price <= 0:
                continue

            # Determine whether the alert should fire
            fired = False
            if sub.condition.operator == AlertOperator.CROSS:
                prev = self._previous_prices.get(sub.id)
                if prev is None:
                    # First tick for this subscription — seed baseline, no fire
                    self._previous_prices[sub.id] = price
                    continue
                # Crossing: was on one side, now on or past the other
                crossed_up = (prev < sub.condition.threshold <= price)
                crossed_down = (prev > sub.condition.threshold >= price)
                fired = crossed_up or crossed_down
                # Always update the baseline for the next tick
                self._previous_prices[sub.id] = price
            else:
                fired = sub.condition.evaluate(price)

            if fired:
                # Double-check the subscription is still alive before firing
                if self.registry.get(sub.id) is None:
                    continue

                callback = self._callbacks.get(sub.id)
                self.registry.mark_fired(sub, price)

                if callback is not None:
                    try:
                        callback(sub)
                    except Exception:
                        pass  # user callback shouldn't crash the engine

                if sub.mode == AlertMode.ONCE:
                    self._callbacks.pop(sub.id, None)
                    self._previous_prices.pop(sub.id, None)

        # If no subscriptions remain for this ticker, cancel market data
        if self.registry.ticker_count(symbol) == 0:
            self._cancel_ticker(symbol)

    def _extract_price(self, ticker: Ticker, field: AlertField) -> Optional[float]:
        """Pull the requested price field from an ib_insync Ticker."""
        if field == AlertField.LAST:
            return ticker.last if ticker.last and ticker.last > 0 else None
        elif field == AlertField.BID:
            return ticker.bid if ticker.bid and ticker.bid > 0 else None
        elif field == AlertField.ASK:
            return ticker.ask if ticker.ask and ticker.ask > 0 else None
        elif field == AlertField.CLOSE:
            return ticker.close if ticker.close and ticker.close > 0 else None
        return None

    def _drain_queue(self) -> None:
        """Process pending add/remove commands from other threads."""
        try:
            while True:
                cmd, arg = self._command_queue.get_nowait()
                if cmd == "ADD":
                    sub = self.registry.get(arg)
                    if sub:
                        self._ensure_ticker_subscribed(sub.ticker)
                elif cmd == "REMOVE":
                    if self.registry.ticker_count(arg) == 0:
                        self._cancel_ticker(arg)
        except queue.Empty:
            pass

    def __repr__(self) -> str:
        return (f"<AlertEngine running={self._running!r} "
                f"tickers={len(self._tickers)} "
                f"subs={self.registry.total_count()}>")


# ── Blocking convenience ──────────────────────────────────────────────────

def run_engine_blocking(engine: AlertEngine) -> None:
    """Run *engine* until KeyboardInterrupt, then clean up.

    Convenience wrapper so callers don't need to remember to call ``stop()``.
    """
    try:
        engine.run()
    except KeyboardInterrupt:
        print("\nAlert engine interrupted. Shutting down...")
    finally:
        engine.stop()
