"""File-based watchlist that auto-subscribes / unsubscribes alerts.

A plain-text file (default: ``alert_watchlist.txt``) acts as shared state
between the backtest server and the alert engine:

- The backtest server (or any process) writes tickers + thresholds to the file.
- :class:`WatchlistMonitor` polls the file and diffs against its in-memory
  state, subscribing new entries and unsubscribing removed ones on the
  attached :class:`AlertEngine`.

Format (one entry per line, ``#`` comments ignored)::

    # alert_watchlist.txt
    AAPL 200.0
    TSLA 180.0 bid
    MSFT 450.0

Each line: ``TICKER  THRESHOLD  [FIELD]``

- *THRESHOLD* is the dollar level to cross.
- *FIELD* is optional; one of ``last`` (default), ``bid``, ``ask``, ``close``.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Set

from .alerts import AlertEngine
from .types import AlertCondition, AlertField, AlertMode, AlertOperator


class WatchlistMonitor:
    """Polls *filepath* on a background thread, keeping the *engine* in sync.

    Args:
        engine: An :class:`AlertEngine` (connected but not necessarily
            running yet — the monitor works before and during ``run()``).
        filepath: Path to the watchlist text file.
        poll_seconds: How often to check the file for changes (default 5 s).

    Typical usage::

        engine = AlertEngine(ib)
        monitor = WatchlistMonitor(engine, "alert_watchlist.txt")
        monitor.start()          # begins background polling
        engine.run()             # blocks; monitor keeps file in sync
    """

    def __init__(
        self,
        engine: AlertEngine,
        filepath: str | Path = "alert_watchlist.txt",
        poll_seconds: float = 5.0,
    ) -> None:
        self._engine = engine
        self._filepath = Path(filepath)
        self._poll_seconds = poll_seconds
        self._active: Dict[str, str] = {}   # ticker -> "THRESHOLD FIELD" (canonical line)
        self._sub_ids: Dict[str, str] = {}  # ticker -> engine subscription id
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        """Begin polling *filepath* on a daemon background thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background thread (does NOT unsubscribe existing alerts)."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._poll_seconds + 2)
            self._thread = None

    # -- public helpers ------------------------------------------------------

    @staticmethod
    def append(filepath: str | Path, ticker: str, threshold: float,
               field: str = "last") -> None:
        """Append a single entry to the watchlist file.

        Convenience for external callers (e.g. a backtest script) so they
        don't need to know the file format.
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = f"{ticker.upper()} {threshold} {field}".strip()
        existing = _read_entries(path)
        if ticker.upper() in existing:
            return  # already present — no-op
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    @staticmethod
    def remove(filepath: str | Path, ticker: str) -> bool:
        """Remove every line for *ticker* from the watchlist file.

        Returns ``True`` if at least one line was removed.
        """
        path = Path(filepath)
        if not path.exists():
            return False
        lines = path.read_text(encoding="utf-8").splitlines()
        ticker_upper = ticker.upper()
        new_lines = []
        removed = False
        for line in lines:
            stripped = line.strip()
            if stripped == "" or stripped.startswith("#"):
                new_lines.append(line)
                continue
            parts = stripped.split()
            if not parts:
                new_lines.append(line)
                continue
            if parts[0].upper() == ticker_upper:
                removed = True
                continue
            new_lines.append(line)
        if removed:
            path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        return removed

    @staticmethod
    def clear(filepath: str | Path) -> None:
        """Remove all entries, keeping comments."""
        path = Path(filepath)
        if not path.exists():
            return
        lines = path.read_text(encoding="utf-8").splitlines()
        kept = [l for l in lines
                if l.strip() == "" or l.strip().startswith("#")]
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")

    # -- internals -----------------------------------------------------------

    def _poll_loop(self) -> None:
        """Background loop — read file, diff, sync."""
        while not self._stop_event.is_set():
            try:
                self._sync()
            except Exception:
                pass  # never let a file-read error kill the thread
            self._stop_event.wait(self._poll_seconds)

    def _sync(self) -> None:
        """Read the file, compare to _active, subscribe/unsubscribe as needed."""
        if not self._filepath.exists():
            # File gone — unsubscribe everything
            if self._active:
                for ticker in list(self._active):
                    self._remove_ticker(ticker)
            return

        on_disk = _read_entries(self._filepath)  # ticker -> canonical line

        disk_tickers = set(on_disk)
        mem_tickers = set(self._active)

        # New tickers → subscribe
        for ticker in disk_tickers - mem_tickers:
            self._add_ticker(ticker, on_disk[ticker])

        # Removed tickers → unsubscribe
        for ticker in mem_tickers - disk_tickers:
            self._remove_ticker(ticker)

        # Changed thresholds → unsubscribe old, subscribe new
        for ticker in disk_tickers & mem_tickers:
            if on_disk[ticker] != self._active[ticker]:
                self._remove_ticker(ticker)
                self._add_ticker(ticker, on_disk[ticker])

    def _add_ticker(self, ticker: str, line: str) -> None:
        """Parse *line* and subscribe via the engine."""
        parts = line.split()
        threshold = float(parts[1])
        field_str = parts[2] if len(parts) >= 3 else "last"

        try:
            field = AlertField(field_str)
        except ValueError:
            field = AlertField.LAST

        condition = AlertCondition(
            field=field,
            operator=AlertOperator.CROSS,
            threshold=threshold,
        )

        sub_id = self._engine.subscribe(
            ticker=ticker,
            condition=condition,
            callback=_watchlist_callback,
            mode=AlertMode.ONCE,
            metadata={"source": "watchlist"},
        )

        self._active[ticker] = line
        self._sub_ids[ticker] = sub_id

    def _remove_ticker(self, ticker: str) -> None:
        """Unsubscribe all engine subscriptions for *ticker*."""
        sub_id = self._sub_ids.pop(ticker, None)
        if sub_id:
            self._engine.unsubscribe(sub_id)
        self._active.pop(ticker, None)


# ── Internal helpers ──────────────────────────────────────────────────────

def _read_entries(path: Path) -> Dict[str, str]:
    """Parse a watchlist file into ``{TICKER: "TICKER THRESHOLD FIELD"}``."""
    entries: Dict[str, str] = {}
    if not path.exists():
        return entries
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) < 2:
            continue
        ticker = parts[0].upper()
        entries[ticker] = stripped
    return entries


def _watchlist_callback(sub) -> None:
    """Default callback for watchlist-fired alerts — prints a timestamped line."""
    from datetime import datetime
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] ALERT  {sub.ticker} crossed {sub.condition.threshold}"
          f" @ ${sub.fire_price:.2f}")
