"""Backend REST + WebSocket API server for ib_paper — listens on port 8081.

REST endpoints::

    GET  /                   — API documentation
    GET  /health             — server + IB connection status
    GET  /account            — account summary
    GET  /positions[/<ticker>] — list positions
    GET  /orders             — list orders
    POST /buy/<ticker>       — place a buy order
    POST /sell/<ticker>      — place a sell order

WebSocket events (emit from client → server)::

    subscribe_price   { "ticker": "AAPL" }     → start receiving real-time quotes
    unsubscribe_price { "ticker": "AAPL" }     → stop receiving quotes
    subscribe_orders  {}                       → live order-status pushes
    subscribe_positions {}                     → live position-update pushes

WebSocket events (server → client pushes)::

    price_update      { ticker, bid, ask, last, close, timestamp }
    order_update      { order_id, symbol, action, qty, type, status, filled, remaining }
    position_update   { symbol, qty, avg_cost, mkt_price, mkt_value, unreal_pnl, pnl_pct }

Start::

    python -m ib_paper.server
    ibpaper-server
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
from typing import Any, Optional

# --- eventlet monkey-patch *must* happen before other imports that touch sockets ---
import eventlet
eventlet.monkey_patch()

from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit, disconnect  # noqa: E402

from .account import AccountService
from .config import Config
from .connection import ConnectionManager
from .exceptions import (
    ConfigError,
    ConnectionError,
    IBPaperError,
    LiveAccountWarning,
    OrderError,
    ValidationError,
)
from .orders import OrderService
from .positions import PositionService
from .types import OrderAction, OrderRequest, OrderType
from .utils import validate_quantity, validate_symbol


# ======================================================================
# Setup
# ======================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger("ibpaper.server")

app = Flask(__name__)
app.config["SECRET_KEY"] = "ibpaper-ws-secret"
socketio = SocketIO(
    app,
    async_mode="eventlet",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)

# ======================================================================
# Global connection state
# ======================================================================

_cm = ConnectionManager()
_lock = threading.Lock()
_reconnect_enabled = True
_last_error: str = ""

# Per-client price subscriptions:  { sid : { ticker : ib_insync.Ticker } }
_price_subs: dict[str, dict[str, Any]] = {}
_subs_lock = threading.Lock()

# Map ticker symbol → contract so we can re-subscribe on reconnect
_ticker_contracts: dict[str, Any] = {}


def _ensure_connected() -> None:
    """Connect to TWS/IB Gateway if not already connected."""
    global _last_error
    with _lock:
        if _cm.is_connected:
            return
        config = Config.load()
        try:
            _cm.connect()
            _last_error = ""
            log.info("Connected to TWS/IB Gateway at %s:%d",
                     config["connection"]["host"], config["connection"]["port"])
            _register_ib_events(_cm.ib)
        except LiveAccountWarning:
            _last_error = (
                f"Port {config['connection']['port']} is a LIVE trading port. "
                "Set safety.confirm_live to false in config, or use port 7497."
            )
            raise ConnectionError(_last_error)
        except ConnectionError:
            _last_error = (
                f"Could not connect to TWS/IB Gateway at "
                f"{config['connection']['host']}:{config['connection']['port']}. "
                "Make sure TWS or IB Gateway is running and API is enabled."
            )
            raise
        except Exception as exc:
            _last_error = str(exc)
            raise ConnectionError(str(exc))


def _ib():
    """Return the connected IB instance, connecting first if needed."""
    _ensure_connected()
    return _cm.ib


# ======================================================================
# Background reconnection
# ======================================================================

def _reconnect_loop() -> None:
    """Continuously attempt to (re)connect with exponential backoff."""
    global _reconnect_enabled
    backoff = 5  # seconds
    while _reconnect_enabled:
        with _lock:
            if not _cm.is_connected:
                try:
                    _cm.connect()
                    _register_ib_events(_cm.ib)
                    log.info("Reconnected to TWS/IB Gateway.")
                    backoff = 5  # reset on success
                except LiveAccountWarning:
                    pass
                except Exception:
                    backoff = min(backoff * 2, 120)  # cap at 2 min
        eventlet.sleep(backoff)


# ======================================================================
# IB → WebSocket event bridge  (registered once on connect)
# ======================================================================

_ib_events_registered = False


def _register_ib_events(ib) -> None:
    """Wire ib_insync events → SocketIO broadcasts (idempotent).

    Price streaming is handled *per-ticker* in _start_price_stream()
    via ``ticker.updateEvent``, not here.  This function sets up the
    session-wide events (order status + position updates).
    """
    global _ib_events_registered
    if _ib_events_registered:
        return
    try:
        # --- order status → order_update for subscribed clients --------------
        def _on_order_status(trade):
            payload = {
                "order_id": trade.order.orderId,
                "symbol": trade.contract.symbol,
                "action": trade.order.action,
                "quantity": trade.order.totalQuantity,
                "order_type": trade.order.orderType,
                "status": trade.orderStatus.status,
                "filled": trade.orderStatus.filled,
                "remaining": trade.orderStatus.remaining,
            }
            socketio.emit("order_update", payload)

        ib.orderStatusEvent += _on_order_status

        # --- position update → position_update broadcast ---------------------
        def _on_update_portfolio(contract, position, marketPrice, marketValue,
                                 averageCost, unrealizedPNL, realizedPNL, accountName):
            cost_basis = float(marketValue) - float(unrealizedPNL)
            pct = (float(unrealizedPNL) / cost_basis * 100) if cost_basis != 0 else 0.0
            payload = {
                "symbol": contract.symbol,
                "quantity": float(position),
                "average_cost": float(averageCost),
                "market_price": float(marketPrice),
                "market_value": float(marketValue),
                "unrealized_pnl": float(unrealizedPNL),
                "realized_pnl": float(realizedPNL),
                "pnl_percent": round(pct, 2),
                "account": accountName,
            }
            socketio.emit("position_update", payload)

        ib.updatePortfolioEvent += _on_update_portfolio

        _ib_events_registered = True
        log.info("IB event bridge registered (order_status / update_portfolio).")
    except AttributeError as exc:
        log.warning("Could not register IB events: %s — will retry on reconnect.", exc)
        _ib_events_registered = False  # allow retry



# ======================================================================
# Market-data helpers
# ======================================================================

def _start_price_stream(ib, sid: str, ticker: str) -> None:
    """Request market data for *ticker* and pipe it to WebSocket *sid*.

    Uses ``ib.reqMktData()`` which returns a ``Ticker`` object.  We attach
    to its ``updateEvent`` so every price change is pushed to the client.
    """
    from ib_insync import Stock
    symbol = ticker.upper()
    contract = Stock(symbol, "SMART", "USD")
    try:
        qualified = ib.qualifyContracts(contract)
        if not qualified:
            log.warning("Could not qualify contract for %s", symbol)
            return
        contract = qualified[0]
    except Exception as exc:
        log.warning("Contract resolution failed for %s: %s", symbol, exc)
        return

    # Request streaming (non-snapshot, streaming)
    tk = ib.reqMktData(contract, "", False, False)

    # Cache contract for re-subscription on reconnect
    _ticker_contracts[symbol] = contract

    def _on_update(t):
        """Push the latest prices to the subscribed WebSocket client."""
        payload = {
            "ticker": symbol,
            "bid": t.bid,
            "ask": t.ask,
            "last": t.last,
            "close": t.close,
            "high": t.high,
            "low": t.low,
            "volume": t.volume,
            "time": str(t.time),
        }
        socketio.emit("price_update", payload, to=sid)

    tk.updateEvent += _on_update

    with _subs_lock:
        _price_subs.setdefault(sid, {})[symbol] = tk

    log.info("WS  %s  subscribed to price stream for %s", sid[:8], symbol)


def _stop_price_stream(ib, sid: str, ticker: str) -> None:
    """Cancel market data for *ticker* on *sid*."""
    symbol = ticker.upper()
    with _subs_lock:
        if sid in _price_subs:
            tk = _price_subs[sid].pop(symbol, None)
        else:
            tk = None

    if tk is not None:
        try:
            if ib:
                ib.cancelMktData(tk.contract)
        except Exception:
            pass
        # Remove updateEvent handlers by disconnecting all (ib_insync Event)
        try:
            tk.updateEvent.clear()
        except Exception:
            pass

    with _subs_lock:
        if sid in _price_subs and not _price_subs[sid]:
            del _price_subs[sid]

    log.info("WS  %s  unsubscribed from price stream for %s", sid[:8], symbol)


def _cleanup_client(sid: str) -> None:
    """Remove all subscriptions for a disconnected client."""
    ib = _cm.ib if _cm.is_connected else None
    with _subs_lock:
        subs = _price_subs.pop(sid, {})
    for symbol, tk in subs.items():
        if ib:
            try:
                ib.cancelMktData(tk.contract)
            except Exception:
                pass
        try:
            tk.updateEvent.clear()
        except Exception:
            pass
    if subs:
        log.info("WS  %s  disconnected — cleaned up %d price stream(s)", sid[:8], len(subs))


# ======================================================================
# Request helpers
# ======================================================================

def _parse_order_body(body: dict[str, Any]) -> tuple[Optional[OrderType], Optional[float], Optional[float], Optional[int], bool]:
    """Parse a buy/sell JSON body. Returns (order_type, limit, stop, qty, sell_all)."""
    order_type: Optional[OrderType] = None
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    qty: Optional[int] = None
    sell_all = False
    
    print(body)

    if "limit" in body and body["limit"] is not None:
        order_type = OrderType.LMT
        raw = body["limit"]
        if isinstance(raw, str) and raw.strip() == "":
            raise ValidationError("Limit price must not be empty.")
        try:
            limit_price = float(raw)
        except (ValueError, TypeError) as exc:
            raise ValidationError(f"Invalid limit price: '{raw}'. Must be a number.") from exc
        if limit_price <= 0:
            raise ValidationError("Limit price must be positive.")
    elif "stop" in body and body["stop"] is not None:
        order_type = OrderType.STP
        raw = body["stop"]
        if isinstance(raw, str) and raw.strip() == "":
            raise ValidationError("Stop price must not be empty.")
        try:
            stop_price = float(raw)
        except (ValueError, TypeError) as exc:
            raise ValidationError(f"Invalid stop price: '{raw}'. Must be a number.") from exc
        if stop_price <= 0:
            raise ValidationError("Stop price must be positive.")
    elif "market" in body:
        order_type = OrderType.MKT
    else:
        raise ValidationError(
            "Request body must contain one of: 'market', 'limit', or 'stop'.\n"
            'Examples: {"market": ""}, {"limit": "150.00"}, {"stop": "145.00"}'
        )

    if "qty" in body and body["qty"] is not None:
        try:
            qty = int(body["qty"])
        except (ValueError, TypeError) as exc:
            raise ValidationError(f"Invalid quantity: '{body['qty']}'.") from exc
        qty = validate_quantity(qty)

    if "all" in body:
        val = body["all"]
        if isinstance(val, bool):
            sell_all = val
        elif isinstance(val, str):
            sell_all = val.lower() in ("true", "1", "yes")
        else:
            sell_all = bool(val)

    return order_type, limit_price, stop_price, qty, sell_all


def _error_response(status_code: int, message: str, details: Any = None) -> tuple:
    """Return a JSON error response tuple for Flask."""
    body: dict[str, Any] = {"error": message}
    if details is not None:
        body["details"] = details
    return jsonify(body), status_code


# ======================================================================
# API documentation
# ======================================================================

_API_DOCS: dict[str, Any] = {
    "service": "ibpaper REST + WebSocket API server",
    "version": "0.2.0",
    "description": "Interactive Brokers paper-trading backend.",
    "rest_endpoints": {
        "GET  /":                 "This documentation.",
        "GET  /health":           "Server + IB connection status.",
        "GET  /account":          "Account summary (NetLiq, Cash, BuyingPower, P&L).",
        "GET  /positions":        "List all open positions.",
        "GET  /positions/<TICKR>":"Show a single position by ticker.",
        "GET  /orders":           "List all orders from this session.",
        "POST /buy/<TICKR>":      "Place a buy order.  See body_formats below.",
        "POST /sell/<TICKR>":     "Place a sell order.  See body_formats below.",
    },
    "ws_events_client_to_server": {
        "subscribe_price":   '{"ticker": "AAPL"}          → start receiving real-time quotes',
        "unsubscribe_price": '{"ticker": "AAPL"}          → stop receiving quotes',
        "subscribe_orders":  "{}                          → live order-status pushes",
        "subscribe_positions": "{}                        → live position-update pushes",
    },
    "ws_events_server_to_client": {
        "price_update":     "{ticker, field, price}              — real-time bid/ask/last/close",
        "order_update":     "{order_id, symbol, action, qty, type, status, filled, remaining}",
        "position_update":  "{symbol, qty, avg_cost, mkt_price, mkt_value, unreal_pnl, pnl_pct}",
    },
    "request_body_formats": {
        "market":    '{"market": ""}                     → market order (default qty)',
        "market_qty":'{"market": "", "qty": 10}          → market order, N shares',
        "limit":     '{"limit": "150.00"}                → limit order @ price',
        "limit_qty": '{"limit": "150.00", "qty": 50}     → limit order, N shares',
        "stop":      '{"stop": "145.00"}                 → stop order @ price',
        "stop_qty":  '{"stop": "145.00", "qty": 25}      → stop order, N shares',
        "sell_all":  '{"market": "", "all": true}        → sell entire position (sell only)',
    },
    "example_curl": {
        "buy_market":  'curl -X POST http://localhost:8081/buy/AAPL -H "Content-Type: application/json" -d \'{"market":""}\'',
        "buy_limit":   'curl -X POST http://localhost:8081/buy/MSFT -H "Content-Type: application/json" -d \'{"limit":"150.00","qty":10}\'',
        "sell_market": 'curl -X POST http://localhost:8081/sell/AAPL -H "Content-Type: application/json" -d \'{"market":"","all":true}\'',
        "health":      'curl http://localhost:8081/health',
        "positions":   'curl http://localhost:8081/positions',
    },
}


# ======================================================================
# REST routes
# ======================================================================

@app.route("/", methods=["GET"])
def api_docs():
    """Return full API documentation."""
    return jsonify(_API_DOCS)


@app.route("/health", methods=["GET"])
def health():
    """Server + IB connection health check."""
    with _lock:
        connected = _cm.is_connected
    config = Config.load()
    status = {
        "server": "running",
        "ib_connected": connected,
        "websocket_clients": len(_price_subs),
        "config": {"host": config["connection"]["host"], "port": config["connection"]["port"]},
    }
    if not connected and _last_error:
        status["last_error"] = _last_error
    http_code = 200 if connected else 503
    return jsonify(status), http_code


@app.route("/account", methods=["GET"])
def account():
    """Return account summary."""
    try:
        ib = _ib()
        snap = AccountService.get_summary(ib)
        return jsonify({
            "net_liquidation": snap.net_liquidation,
            "total_cash": snap.total_cash,
            "buying_power": snap.buying_power,
            "available_funds": snap.available_funds,
            "gross_pnl": snap.gross_pnl,
            "realized_pnl": snap.realized_pnl,
            "unrealized_pnl": snap.unrealized_pnl,
            "currency": snap.currency,
        })
    except ConnectionError as exc:
        return _error_response(503, str(exc))
    except IBPaperError as exc:
        return _error_response(500, str(exc))


@app.route("/positions", methods=["GET"])
@app.route("/positions/<ticker>", methods=["GET"])
def positions(ticker: Optional[str] = None):
    """List all positions, or a single position by ticker."""
    try:
        ib = _ib()
        all_pos = PositionService.list_positions(ib)
    except ConnectionError as exc:
        return _error_response(503, str(exc))
    except IBPaperError as exc:
        return _error_response(500, str(exc))

    if ticker:
        ticker = ticker.upper()
        all_pos = [p for p in all_pos if p.symbol.upper() == ticker]
        if not all_pos:
            return _error_response(404, f"No position found for '{ticker}'.")

    result = []
    for p in all_pos:
        cost_basis = p.market_value - p.unrealized_pnl
        pct = (p.unrealized_pnl / cost_basis * 100) if cost_basis != 0 else 0.0
        result.append({
            "symbol": p.symbol,
            "quantity": p.quantity,
            "average_cost": p.average_cost,
            "market_price": p.market_price,
            "market_value": p.market_value,
            "unrealized_pnl": p.unrealized_pnl,
            "realized_pnl": p.realized_pnl,
            "pnl_percent": round(pct, 2),
            "account": p.account,
        })
    return jsonify(result)


@app.route("/orders", methods=["GET"])
def orders():
    """List all orders from the current session."""
    try:
        ib = _ib()
        all_trades = OrderService.get_all_orders(ib)
    except ConnectionError as exc:
        return _error_response(503, str(exc))
    except IBPaperError as exc:
        return _error_response(500, str(exc))

    result = []
    for t in all_trades:
        result.append({
            "order_id": t.order.orderId,
            "symbol": t.contract.symbol,
            "action": t.order.action,
            "quantity": t.order.totalQuantity,
            "order_type": t.order.orderType,
            "status": t.orderStatus.status,
            "filled": t.orderStatus.filled,
            "remaining": t.orderStatus.remaining,
            "limit_price": getattr(t.order, "lmtPrice", None),
            "stop_price": getattr(t.order, "auxPrice", None),
        })
    return jsonify(result)


@app.route("/buy/<ticker>", methods=["POST"])
def buy(ticker: str):
    """Place a buy order."""
    try:
        ticker = validate_symbol(ticker)
    except ValidationError as exc:
        return _error_response(400, str(exc))

    body = request.get_json(silent=True) or {}
    try:
        order_type, limit_price, stop_price, qty, _ = _parse_order_body(body)
    except ValidationError as exc:
        return _error_response(400, str(exc))

    if qty is None:
        qty = Config.get("defaults", "order_quantity", default=100)

    req = OrderRequest(
        symbol=ticker, action=OrderAction.BUY, total_quantity=qty,
        order_type=order_type,  # type: ignore[arg-type]
        limit_price=limit_price, stop_price=stop_price,
    )

    try:
        ib = _ib()
        trade = OrderService.place_order(ib, req)
        log.info("BUY  %s  qty=%d  type=%s  id=%d", ticker, qty, order_type.value, trade.order.orderId)
        return jsonify({
            "order_id": trade.order.orderId, "symbol": ticker, "action": "BUY",
            "quantity": qty, "order_type": order_type.value,
            "limit_price": limit_price, "stop_price": stop_price,
            "status": trade.orderStatus.status,
            "filled": trade.orderStatus.filled, "remaining": trade.orderStatus.remaining,
        }), 201
    except ConnectionError as exc:
        return _error_response(503, str(exc))
    except OrderError as exc:
        return _error_response(422, str(exc))
    except IBPaperError as exc:
        return _error_response(500, str(exc))


@app.route("/sell/<ticker>", methods=["POST"])
def sell(ticker: str):
    """Place a sell order."""
    try:
        ticker = validate_symbol(ticker)
    except ValidationError as exc:
        return _error_response(400, str(exc))

    body = request.get_json(silent=True) or {}
    try:
        order_type, limit_price, stop_price, qty, sell_all = _parse_order_body(body)
    except ValidationError as exc:
        return _error_response(400, str(exc))

    if sell_all:
        if qty is not None:
            return _error_response(400, "Use either 'all' or 'qty', not both.")
        try:
            ib = _ib()
            pos = PositionService.get_position(ib, ticker)
            if pos is None:
                return _error_response(404, f"No position found for '{ticker}'. Nothing to sell.")
            qty = int(abs(pos.quantity))
        except ConnectionError as exc:
            return _error_response(503, str(exc))
        except IBPaperError as exc:
            return _error_response(500, str(exc))

    if qty is None:
        try:
            ib = _ib()
            pos = PositionService.get_position(ib, ticker)
            if pos is not None:
                qty = int(abs(pos.quantity))
            else:
                return _error_response(400,
                    f"No position found for '{ticker}' and no 'qty' specified. "
                    "Provide 'qty' or use 'all': true.")
        except ConnectionError as exc:
            return _error_response(503, str(exc))
        except IBPaperError as exc:
            return _error_response(500, str(exc))

    req = OrderRequest(
        symbol=ticker, action=OrderAction.SELL, total_quantity=qty,
        order_type=order_type,  # type: ignore[arg-type]
        limit_price=limit_price, stop_price=stop_price,
    )

    try:
        ib = _ib()
        trade = OrderService.place_order(ib, req)
        log.info("SELL %s  qty=%d  type=%s  id=%d", ticker, qty, order_type.value, trade.order.orderId)
        return jsonify({
            "order_id": trade.order.orderId, "symbol": ticker, "action": "SELL",
            "quantity": qty, "order_type": order_type.value,
            "limit_price": limit_price, "stop_price": stop_price,
            "status": trade.orderStatus.status,
            "filled": trade.orderStatus.filled, "remaining": trade.orderStatus.remaining,
        }), 201
    except ConnectionError as exc:
        return _error_response(503, str(exc))
    except OrderError as exc:
        return _error_response(422, str(exc))
    except IBPaperError as exc:
        return _error_response(500, str(exc))


# ======================================================================
# Error handlers
# ======================================================================

@app.errorhandler(404)
def _not_found(_error):
    """Catch-all for unmatched routes — returns endpoint list."""
    return jsonify({
        "error": "Not found. See available endpoints below.",
        **({"rest_endpoints": _API_DOCS["rest_endpoints"]} if "rest_endpoints" in _API_DOCS else {}),
    }), 404


@app.errorhandler(405)
def _method_not_allowed(_error):
    return _error_response(405, "Method not allowed.")


@app.errorhandler(500)
def _internal_error(_error):
    return _error_response(500, "Internal server error.")


@app.before_request
def _log_request():
    """Log every incoming REST request."""
    log.info("%s %s  %s", request.method, request.path, request.remote_addr)


# ======================================================================
# WebSocket events
# ======================================================================

@socketio.on("connect")
def _ws_connect():
    """Client connected via WebSocket."""
    log.info("WS  %s  connected", request.sid[:8])


@socketio.on("disconnect")
def _ws_disconnect():
    """Client disconnected — clean up subscriptions."""
    _cleanup_client(request.sid)
    log.info("WS  %s  disconnected", request.sid[:8])


@socketio.on("subscribe_price")
def _ws_subscribe_price(data: dict):
    """Client wants real-time quotes for a ticker.

    Expects: ``{"ticker": "AAPL"}``
    """
    ticker = data.get("ticker", "").upper().strip()
    if not ticker:
        emit("error", {"error": "Missing 'ticker' field."})
        return
    try:
        ib = _ib()
        _start_price_stream(ib, request.sid, ticker)
        emit("subscribed", {"ticker": ticker, "event": "price_update"})
    except ConnectionError as exc:
        emit("error", {"error": str(exc)})


@socketio.on("unsubscribe_price")
def _ws_unsubscribe_price(data: dict):
    """Client wants to stop receiving quotes for a ticker.

    Expects: ``{"ticker": "AAPL"}``
    """
    ticker = data.get("ticker", "").upper().strip()
    if not ticker:
        emit("error", {"error": "Missing 'ticker' field."})
        return
    try:
        ib = _ib()
        _stop_price_stream(ib, request.sid, ticker)
        emit("unsubscribed", {"ticker": ticker})
    except ConnectionError:
        # Even if not connected, clean up tracking
        _stop_price_stream(None, request.sid, ticker)
        emit("unsubscribed", {"ticker": ticker})


@socketio.on("subscribe_orders")
def _ws_subscribe_orders(_data: Optional[dict] = None):
    """Client wants live order-status updates.

    Once subscribed, ``order_update`` events will be pushed automatically
    whenever any order status changes in TWS.
    """
    log.info("WS  %s  subscribed to order updates", request.sid[:8])
    emit("subscribed", {"event": "order_update"})


@socketio.on("subscribe_positions")
def _ws_subscribe_positions(_data: Optional[dict] = None):
    """Client wants live position updates.

    Once subscribed, ``position_update`` events will be pushed automatically
    whenever the portfolio changes in TWS.
    """
    log.info("WS  %s  subscribed to position updates", request.sid[:8])
    emit("subscribed", {"event": "position_update"})


# ======================================================================
# Startup
# ======================================================================

def _startup():
    """Called before the first request — attempt initial connection."""
    try:
        _ensure_connected()
    except ConnectionError as exc:
        log.warning("Initial connection failed: %s", exc)
        log.info("Background reconnection thread will keep trying...")

    t = threading.Thread(target=_reconnect_loop, daemon=True)
    t.start()


_startup_called = False
_original_dispatch = app.full_dispatch_request


def _dispatch_with_startup():
    global _startup_called
    if not _startup_called:
        _startup_called = True
        _startup()
    return _original_dispatch()


app.full_dispatch_request = _dispatch_with_startup


# ======================================================================
# Entry points
# ======================================================================

def run_server(host: str = "0.0.0.0", port: int = 8081, debug: bool = False) -> None:
    """Start the REST + WebSocket server."""
    log.info("=============================================")
    log.info("  ibpaper REST + WebSocket API server")
    log.info("  Listening on http://%s:%d", host, port)
    log.info("=============================================")
    log.info("  REST endpoints:")
    log.info("    GET  /")
    log.info("    GET  /health")
    log.info("    GET  /account")
    log.info("    GET  /positions[/<ticker>]")
    log.info("    GET  /orders")
    log.info("    POST /buy/<ticker>")
    log.info("    POST /sell/<ticker>")
    log.info("  WebSocket events:")
    log.info("    subscribe_price / unsubscribe_price")
    log.info("    subscribe_orders / subscribe_positions")
    log.info("    → price_update / order_update / position_update")
    log.info("=============================================")

    if not debug:
        import flask.cli
        flask.cli.show_server_banner = lambda *a, **k: None  # type: ignore[assignment]

    socketio.run(app, host=host, port=port, debug=debug)


def main() -> None:
    """CLI entry point — parses -h / --help and starts the server."""
    parser = argparse.ArgumentParser(
        prog="ibpaper-server",
        description="ibpaper REST + WebSocket API server — IB paper-trading backend.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "REST endpoints:\n"
            "  GET  /                   API documentation\n"
            "  GET  /health             Server + IB connection status\n"
            "  GET  /account            Account summary\n"
            "  GET  /positions[/<TICKR>]  List positions\n"
            "  GET  /orders             List orders\n"
            "  POST /buy/<TICKR>        Place a buy order\n"
            "  POST /sell/<TICKR>       Place a sell order\n"
            "\n"
            "WebSocket events (client → server):\n"
            "  subscribe_price     {\"ticker\": \"AAPL\"}\n"
            "  unsubscribe_price   {\"ticker\": \"AAPL\"}\n"
            "  subscribe_orders    {}\n"
            "  subscribe_positions {}\n"
            "\n"
            "WebSocket events (server → client):\n"
            "  price_update        {ticker, field, price}\n"
            "  order_update        {order_id, symbol, action, qty, type, status, ...}\n"
            "  position_update     {symbol, qty, avg_cost, mkt_price, mkt_value, ...}\n"
            "\n"
            "Request body formats (JSON for POST /buy /sell):\n"
            '  {"market": ""}                     market order\n'
            '  {"market": "", "qty": 10}          market order, N shares\n'
            '  {"limit": "150.00"}                limit order\n'
            '  {"limit": "150.00", "qty": 50}     limit order, N shares\n'
            '  {"stop": "145.00"}                 stop order\n'
            '  {"stop": "145.00", "qty": 25}      stop order, N shares\n'
            '  {"market": "", "all": true}        sell entire position (sell only)\n'
            "\n"
            "Examples:\n"
            "  ibpaper-server\n"
            "  ibpaper-server --port 8081\n"
            "  ibpaper-server --host 127.0.0.1 --port 8082\n"
        ),
    )
    parser.add_argument("-H", "--host", default="0.0.0.0",
                        help="Bind address (default: 0.0.0.0).")
    parser.add_argument("-p", "--port", type=int, default=8081,
                        help="TCP port (default: 8081).")
    parser.add_argument("--debug", action="store_true", default=False,
                        help="Enable debug mode (NEVER in production).")
    args = parser.parse_args()
    run_server(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
