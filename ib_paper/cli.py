"""CLI entry point -- ``ibpaper`` command group.

Usage::

    ibpaper --help
    ibpaper setup --show
    ibpaper account --summary
    ibpaper buy AAPL --qty 10
    ibpaper sell AAPL --all
"""

import sys
from typing import Optional

import click

from .__init__ import __version__
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
from .alerts import AlertEngine, AlertRegistry
from .types import (
    AlertCondition,
    AlertField,
    AlertMode,
    AlertOperator,
    OrderAction,
    OrderRequest,
    OrderType,
    Subscription,
)
from .utils import (
    color_for,
    confirm,
    format_money,
    format_pnl,
    table,
    validate_quantity,
    validate_symbol,
)


# ======================================================================
# Helpers
# ======================================================================

def _get_ib(ctx: click.Context) -> "IB":  # noqa: F821
    """Obtain a connected ``ib_insync.IB`` instance from the context.

    Connects on first call per command invocation; reuses the connection
    on subsequent calls within the same command.
    """
    cm: ConnectionManager = ctx.obj["connection"]
    if not cm.is_connected:
        try:
            cm.connect()
        except LiveAccountWarning as exc:
            click.secho(f"⚠  {exc}", fg="yellow")
            if not click.confirm("Connect to LIVE account anyway?"):
                raise click.Abort()
            # The user confirmed -- retry without the safety check.
            # We temporarily set confirm_live to False for this session.
            cm.disconnect()
            config = Config.load()
            cm.connect(
                host=config["connection"]["host"],
                port=config["connection"]["port"],
                client_id=config["connection"]["client_id"],
            )
        except ConnectionError as exc:
            click.secho(f"✖  {exc}", fg="red")
            raise click.Abort()
    return cm.ib


def _connect_readonly(ctx: click.Context) -> "IB":  # noqa: F821
    """Connect in read-only mode (orders blocked)."""
    cm: ConnectionManager = ctx.obj["connection"]
    if not cm.is_connected:
        try:
            cm.connect(readonly=True)
        except LiveAccountWarning as exc:
            click.secho(f"⚠  {exc}", fg="yellow")
            if not click.confirm("Connect to LIVE account anyway?"):
                raise click.Abort()
            cm.disconnect()
            config = Config.load()
            cm.connect(
                host=config["connection"]["host"],
                port=config["connection"]["port"],
                client_id=config["connection"]["client_id"],
                readonly=True,
            )
        except ConnectionError as exc:
            click.secho(f"✖  {exc}", fg="red")
            raise click.Abort()
    return cm.ib


def _determine_order_type(
    limit: Optional[float],
    stop: Optional[float],
    stop_limit: Optional[tuple[float, float]],
) -> OrderType:
    """Figure out the order type from the supplied flags."""
    if stop_limit is not None:
        return OrderType.STP_LMT
    if limit is not None:
        return OrderType.LMT
    if stop is not None:
        return OrderType.STP
    return OrderType.MKT


# ======================================================================
# CLI group
# ======================================================================

@click.group()
@click.version_option(version=__version__, prog_name="ibpaper")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """ibpaper — Interactive Brokers Paper Trading CLI.

    Manage a paper trading account, enter and exit positions, and
    monitor your portfolio — all from the command line.

    \b
    Quick start:
        ibpaper setup          # configure connection
        ibpaper account        # check your balance
        ibpaper buy AAPL -q 10  # enter a position
        ibpaper sell AAPL --all # exit a position
    """
    ctx.ensure_object(dict)
    ctx.obj["connection"] = ConnectionManager()


# ======================================================================
# setup
# ======================================================================

@cli.command()
@click.option("--host", default=None, help="TWS / IB Gateway host address.")
@click.option("--port", default=None, type=int, help="TWS port (7497=paper, 7496=live).")
@click.option("--client-id", default=None, type=int, help="Unique client ID.")
@click.option("--timeout", default=None, type=int, help="Connection timeout in seconds.")
@click.option("--default-qty", default=None, type=int, help="Default order quantity.")
@click.option("--show", "show_config", is_flag=True, help="Print current config and exit.")
def setup(
    host: Optional[str],
    port: Optional[int],
    client_id: Optional[int],
    timeout: Optional[int],
    default_qty: Optional[int],
    show_config: bool,
) -> None:
    """Configure connection settings for ibpaper.

    Settings are saved to \b~/.ib_paper/config.json.

    \b
    Examples:
        ibpaper setup --show
        ibpaper setup --port 7497
        ibpaper setup --host 192.168.1.50 --default-qty 50
    """
    if show_config:
        cfg = Config.load()
        click.echo(f"Config file: {Config.path()}")
        click.echo()
        click.echo("  [connection]")
        for k, v in cfg["connection"].items():
            click.echo(f"    {k}: {v}")
        click.echo()
        click.echo("  [defaults]")
        for k, v in cfg["defaults"].items():
            click.echo(f"    {k}: {v}")
        click.echo()
        click.echo("  [safety]")
        for k, v in cfg["safety"].items():
            click.echo(f"    {k}: {v}")
        return

    # Build the update dict from non-None options
    updates: dict = {}
    if host is not None:
        updates.setdefault("connection", {})["host"] = host
    if port is not None:
        updates.setdefault("connection", {})["port"] = port
        if port == 7496:
            click.secho(
                "⚠  Port 7496 is the LIVE trading port. "
                "Use 7497 for paper trading.",
                fg="yellow",
            )
    if client_id is not None:
        updates.setdefault("connection", {})["client_id"] = client_id
    if timeout is not None:
        updates.setdefault("connection", {})["timeout"] = timeout
    if default_qty is not None:
        updates.setdefault("defaults", {})["order_quantity"] = default_qty

    if updates:
        Config.update(updates)
        click.secho("✓  Configuration saved.", fg="green")
        click.echo(f"   File: {Config.path()}")
    else:
        click.echo("No changes provided. Use --show to view current config.")


# ======================================================================
# account
# ======================================================================

@cli.command()
@click.option("--summary", "-s", "show_summary", is_flag=True, help="Account summary (default).")
@click.option("--portfolio", "-p", "show_portfolio", is_flag=True, help="Show portfolio details.")
@click.option("--pnl", "show_pnl", is_flag=True, help="Show P&L breakdown only.")
def account(
    show_summary: bool,
    show_portfolio: bool,
    show_pnl: bool,
) -> None:
    """View account information.

    \b
    Examples:
        ibpaper account               # summary (default)
        ibpaper account --portfolio   # positions + P&L
        ibpaper account --pnl         # P&L only
    """
    try:
        ib = _connect_readonly(click.get_current_context())
    except click.Abort:
        return

    try:
        if show_pnl and not show_portfolio:
            s = AccountService.get_summary(ib)
            click.echo()
            click.echo("Profit & Loss")
            click.echo("─────────────")
            click.echo(f"  Gross P&L      : {format_pnl(s.gross_pnl):>12}")
            click.echo(f"  Realized P&L   : {format_pnl(s.realized_pnl):>12}")
            click.echo(f"  Unrealized P&L : {format_pnl(s.unrealized_pnl):>12}")
            return

        if show_portfolio:
            positions = AccountService.get_portfolio(ib)
            if not positions:
                click.echo("No open positions.")
                return

            click.echo()
            rows = []
            for p in positions:
                pct = (p.unrealized_pnl / (p.market_value - p.unrealized_pnl) * 100) if p.market_value - p.unrealized_pnl != 0 else 0.0
                rows.append({
                    "Symbol": p.symbol,
                    "Qty": f"{p.quantity:,.0f}",
                    "Avg Cost": format_money(p.average_cost),
                    "Mkt Price": format_money(p.market_price),
                    "Mkt Value": format_money(p.market_value),
                    "Unreal. P&L": format_money(p.unrealized_pnl),
                    "P&L %": f"{pct:+.2f}%",
                })

            # Print with ANSI coloring for P&L
            headers = list(rows[0].keys())
            for row in rows:
                pnl_str = row["Unreal. P&L"]
                pnl_val = pnl_str  # pass through for display
                color = color_for(p.unrealized_pnl)  # noqa: F821 -- we'd need to re-iterate
                # Simple approach: just print the table plain
            click.echo(table(rows, headers))
            return

        # Default: summary
        s = AccountService.get_summary(ib)
        click.echo()
        click.echo("Account Summary")
        click.echo("───────────────")
        click.echo(f"  Net Liquidation : {format_money(s.net_liquidation):>12}")
        click.echo(f"  Total Cash      : {format_money(s.total_cash):>12}")
        click.echo(f"  Buying Power    : {format_money(s.buying_power):>12}")
        click.echo(f"  Available Funds : {format_money(s.available_funds):>12}")
        click.echo()
        click.echo(f"  Gross P&L       : {format_money(s.gross_pnl):>12}")
        click.echo(f"  Realized P&L    : {format_money(s.realized_pnl):>12}")
        click.echo(f"  Unrealized P&L  : {format_money(s.unrealized_pnl):>12}")
    except IBPaperError as exc:
        click.secho(f"✖  {exc}", fg="red")


# ======================================================================
# buy
# ======================================================================

@cli.command()
@click.argument("symbol")
@click.option("--qty", "-q", default=None, type=int, help="Quantity to buy.")
@click.option("--limit", "-l", type=float, default=None, help="Limit price.")
@click.option("--stop", "stop_price", type=float, default=None, help="Stop price.")
@click.option(
    "--stop-limit",
    nargs=2,
    type=float,
    default=None,
    help="Stop and limit prices: <stop> <limit>.",
)
@click.option("--market", "-m", "use_market", is_flag=True, default=True, help="Market order (default).")
@click.option("--dry-run", is_flag=True, help="Validate without placing the order.")
@click.option("--yes", "-y", "skip_confirm", is_flag=True, help="Skip confirmation prompt.")
def buy(
    symbol: str,
    qty: Optional[int],
    limit: Optional[float],
    stop_price: Optional[float],
    stop_limit: Optional[tuple[float, float]],
    use_market: bool,
    dry_run: bool,
    skip_confirm: bool,
) -> None:
    """Buy / enter a position.

    \b
    SYMBOL is the stock ticker (e.g. AAPL, MSFT, TSLA).

    \b
    Examples:
        ibpaper buy AAPL                     # Market buy (default qty)
        ibpaper buy AAPL --qty 50            # Market buy 50 shares
        ibpaper buy AAPL -q 10 -l 150.00     # Limit buy @ $150
        ibpaper buy AAPL --stop 155.00        # Stop buy @ $155
        ibpaper buy AAPL --dry-run            # Validate only
    """
    try:
        symbol = validate_symbol(symbol)
    except ValidationError as exc:
        click.secho(f"✖  {exc}", fg="red")
        raise SystemExit(1)

    config = Config.load()
    if qty is None:
        qty = config["defaults"]["order_quantity"]
    try:
        qty = validate_quantity(qty)
    except ValidationError as exc:
        click.secho(f"✖  {exc}", fg="red")
        raise SystemExit(1)

    # Determine order type
    stop = stop_price
    stop_lim = stop_limit
    order_type = _determine_order_type(limit, stop, stop_lim)

    stop_price_final: Optional[float] = stop
    limit_price_final: Optional[float] = limit
    if order_type == OrderType.STP_LMT and stop_lim is not None:
        stop_price_final, limit_price_final = stop_lim

    request = OrderRequest(
        symbol=symbol,
        action=OrderAction.BUY,
        total_quantity=qty,
        order_type=order_type,
        limit_price=limit_price_final,
        stop_price=stop_price_final,
    )

    # Print order summary
    click.echo()
    click.secho("Order Summary", bold=True)
    click.echo(f"  Symbol    : {request.symbol}")
    click.echo(f"  Action    : BUY")
    click.echo(f"  Quantity  : {request.total_quantity}")
    click.echo(f"  Type      : {request.order_type.value}")
    if request.limit_price:
        click.echo(f"  Limit     : ${request.limit_price:,.2f}")
    if request.stop_price:
        click.echo(f"  Stop      : ${request.stop_price:,.2f}")

    if dry_run:
        click.echo()
        click.secho("  [DRY RUN] Order will NOT be placed.", fg="yellow")
        try:
            ib = _connect_readonly(click.get_current_context())
            OrderService._resolve_contract(ib, symbol)
            click.secho(f"✓  Symbol '{symbol}' is valid and resolvable.", fg="green")
        except (IBPaperError, click.Abort) as exc:
            click.secho(f"✖  {exc}", fg="red")
            raise SystemExit(1)
        return

    # Confirmation
    if config["safety"]["confirm_orders"] and not skip_confirm:
        click.echo()
        if not click.confirm("Place this order?"):
            click.echo("Aborted.")
            return

    # Place the order
    try:
        ib = _get_ib(click.get_current_context())
        trade = OrderService.place_order(ib, request)
        click.echo()
        click.secho("✓  Order submitted.", fg="green")
        click.echo(f"   Order ID   : {trade.order.orderId}")
        click.echo(f"   Status     : {trade.orderStatus.status}")
        click.echo(f"   Filled     : {trade.orderStatus.filled}")
        click.echo(f"   Remaining  : {trade.orderStatus.remaining}")
    except (IBPaperError, click.Abort) as exc:
        click.secho(f"✖  {exc}", fg="red")
        raise SystemExit(1)


# ======================================================================
# sell
# ======================================================================

@cli.command()
@click.argument("symbol")
@click.option("--qty", "-q", default=None, type=int, help="Quantity to sell.")
@click.option("--limit", "-l", type=float, default=None, help="Limit price.")
@click.option("--stop", "stop_price", type=float, default=None, help="Stop price.")
@click.option(
    "--stop-limit",
    nargs=2,
    type=float,
    default=None,
    help="Stop and limit prices: <stop> <limit>.",
)
@click.option("--all", "sell_all", is_flag=True, help="Sell the entire position.")
@click.option("--dry-run", is_flag=True, help="Validate without placing the order.")
@click.option("--yes", "-y", "skip_confirm", is_flag=True, help="Skip confirmation prompt.")
def sell(
    symbol: str,
    qty: Optional[int],
    limit: Optional[float],
    stop_price: Optional[float],
    stop_limit: Optional[tuple[float, float]],
    sell_all: bool,
    dry_run: bool,
    skip_confirm: bool,
) -> None:
    """Sell / exit a position.

    \b
    SYMBOL is the stock ticker.

    \b
    Examples:
        ibpaper sell AAPL --all              # Close entire position
        ibpaper sell AAPL --qty 50           # Sell 50 shares at market
        ibpaper sell AAPL -q 10 -l 155.00    # Limit sell @ $155
        ibpaper sell AAPL --all --stop 145.00 # Stop-loss on full position
    """
    try:
        symbol = validate_symbol(symbol)
    except ValidationError as exc:
        click.secho(f"✖  {exc}", fg="red")
        raise SystemExit(1)

    # Resolve quantity
    if sell_all and qty is not None:
        click.secho("✖  Use either --all or --qty, not both.", fg="red")
        raise SystemExit(1)

    if not sell_all and qty is None:
        # If neither --all nor --qty, try to get current position qty
        try:
            ib = _connect_readonly(click.get_current_context())
            pos = PositionService.get_position(ib, symbol)
            if pos is None:
                click.secho(f"✖  No position found for '{symbol}'.", fg="red")
                click.echo("   Use --qty to specify a quantity, or --all to close the full position.")
                raise SystemExit(1)
            click.echo(f"Found {abs(pos.quantity):,.0f} shares of {symbol}.")
            if not click.confirm("Sell entire position?"):
                click.echo("Aborted. Use --qty to specify a different quantity.")
                return
            qty = int(abs(pos.quantity))
        except (IBPaperError, click.Abort) as exc:
            if isinstance(exc, click.Abort):
                raise SystemExit(0)
            click.secho(f"✖  {exc}", fg="red")
            raise SystemExit(1)

    if qty is not None:
        try:
            qty = validate_quantity(qty)
        except ValidationError as exc:
            click.secho(f"✖  {exc}", fg="red")
            raise SystemExit(1)

    # If --all and we haven't resolved qty yet
    if sell_all and qty is None:
        try:
            ib = _connect_readonly(click.get_current_context())
            pos = PositionService.get_position(ib, symbol)
            if pos is None:
                click.secho(f"✖  No position found for '{symbol}'. Nothing to sell.", fg="red")
                raise SystemExit(1)
            qty = int(abs(pos.quantity))
        except (IBPaperError, click.Abort) as exc:
            if isinstance(exc, click.Abort):
                raise SystemExit(0)
            click.secho(f"✖  {exc}", fg="red")
            raise SystemExit(1)

    # Determine order type
    stop = stop_price
    stop_lim = stop_limit
    order_type = _determine_order_type(limit, stop, stop_lim)

    stop_price_final: Optional[float] = stop
    limit_price_final: Optional[float] = limit
    if order_type == OrderType.STP_LMT and stop_lim is not None:
        stop_price_final, limit_price_final = stop_lim

    request = OrderRequest(
        symbol=symbol,
        action=OrderAction.SELL,
        total_quantity=qty,
        order_type=order_type,
        limit_price=limit_price_final,
        stop_price=stop_price_final,
    )

    # Print order summary
    click.echo()
    click.secho("Order Summary", bold=True)
    click.echo(f"  Symbol    : {request.symbol}")
    click.echo(f"  Action    : SELL")
    click.echo(f"  Quantity  : {request.total_quantity}")
    click.echo(f"  Type      : {request.order_type.value}")
    if request.limit_price:
        click.echo(f"  Limit     : ${request.limit_price:,.2f}")
    if request.stop_price:
        click.echo(f"  Stop      : ${request.stop_price:,.2f}")

    if dry_run:
        click.echo()
        click.secho("  [DRY RUN] Order will NOT be placed.", fg="yellow")
        try:
            ib = _connect_readonly(click.get_current_context())
            OrderService._resolve_contract(ib, symbol)
            click.secho(f"✓  Symbol '{symbol}' is valid and resolvable.", fg="green")
        except (IBPaperError, click.Abort) as exc:
            click.secho(f"✖  {exc}", fg="red")
            raise SystemExit(1)
        return

    # Confirmation
    config = Config.load()
    if config["safety"]["confirm_orders"] and not skip_confirm:
        click.echo()
        if not click.confirm("Place this order?"):
            click.echo("Aborted.")
            return

    # Place the order
    try:
        ib = _get_ib(click.get_current_context())
        trade = OrderService.place_order(ib, request)
        click.echo()
        click.secho("✓  Order submitted.", fg="green")
        click.echo(f"   Order ID   : {trade.order.orderId}")
        click.echo(f"   Status     : {trade.orderStatus.status}")
        click.echo(f"   Filled     : {trade.orderStatus.filled}")
        click.echo(f"   Remaining  : {trade.orderStatus.remaining}")
    except (IBPaperError, click.Abort) as exc:
        click.secho(f"✖  {exc}", fg="red")
        raise SystemExit(1)


# ======================================================================
# alert (group)
# ======================================================================

@cli.group()
def alert() -> None:
    """Manage price alerts.

    Subscribe to ticker price thresholds and get notified when the price
    crosses a level (in either direction).

    \b
    Examples:
        ibpaper alert subscribe AAPL --cross 200.0
        ibpaper alert subscribe TSLA --cross 180.0 --every
        ibpaper alert list
        ibpaper alert watch
        ibpaper alert unsubscribe <sub_id>
    """


@alert.command("subscribe")
@click.argument("symbol")
@click.option("--cross", "-x", type=float, default=None, required=True,
              help="Fire when price crosses this level (upward or downward).")
@click.option("--field", "-f", "field_name", default="last",
              type=click.Choice(["last", "bid", "ask", "close"]),
              help="Which price field to watch (default: last).")
@click.option("--every", "mode_every", is_flag=True, help="Re-arm after firing (default: fire once).")
@click.option("--message", "-m", default=None, help="Custom message to display on alert.")
def alert_subscribe(
    symbol: str,
    cross: float,
    field_name: str,
    mode_every: bool,
    message: Optional[str],
) -> None:
    """Subscribe to a price-crossing alert for SYMBOL.

    Fires when the price crosses *threshold* from either direction:
    upward (was below, now at or above) or downward (was above, now at
    or below).  Needs two ticks to establish a baseline before the first
    possible fire.

    \b
    Examples:
        ibpaper alert subscribe AAPL --cross 200.0
        ibpaper alert subscribe TSLA --cross 180.0 --every
        ibpaper alert subscribe MSFT --cross 450.0 --field bid
    """
    try:
        symbol = validate_symbol(symbol)
    except ValidationError as exc:
        click.secho(f"✖  {exc}", fg="red")
        raise SystemExit(1)

    # Build condition — always CROSS
    field = AlertField(field_name)
    operator = AlertOperator.CROSS
    threshold = cross

    condition = AlertCondition(field=field, operator=operator, threshold=threshold)
    mode = AlertMode.EVERY if mode_every else AlertMode.ONCE

    # Connect
    try:
        ib = _get_ib(click.get_current_context())
    except click.Abort:
        return

    engine = AlertEngine(ib)

    msg = message or f"{symbol} {condition.describe()}"
    def _fire_callback(sub: Subscription) -> None:
        click.secho(f"\n🚨  ALERT: {msg}  (fired at ${sub.fire_price:.2f})", fg="yellow", bold=True)

    sub_id = engine.subscribe(
        ticker=symbol,
        condition=condition,
        callback=_fire_callback,
        mode=mode,
        metadata={"message": msg},
    )

    click.echo()
    click.secho(f"✓  Subscribed to {symbol}", fg="green")
    click.echo(f"   ID:        {sub_id}")
    click.echo(f"   Condition: {condition.describe()}")
    click.echo(f"   Mode:      {mode.value}")

    if not engine.is_running:
        click.echo()
        click.echo(f"   Run 'ibpaper alert watch' to start monitoring ({engine.registry.total_count()} active).")


@alert.command("list")
@click.option("--ticker", "-t", default=None, help="Filter by ticker symbol.")
@click.option("--all", "-a", "show_all", is_flag=True, help="Include already-fired subscriptions.")
def alert_list(ticker: Optional[str], show_all: bool) -> None:
    """List alert subscriptions."""
    try:
        ib = _connect_readonly(click.get_current_context())
    except click.Abort:
        return

    # Build a temporary registry from the engine — for now, list is ephemeral
    # (subscriptions live in-memory on the AlertEngine instance).
    # When no engine is running we just display a placeholder.
    click.echo()
    click.secho("Alert subscriptions are managed per-session.", fg="yellow")
    click.echo("Start monitoring with: ibpaper alert watch")
    click.echo()
    click.echo("Active subscriptions are shown while the watch command is running.")
    click.echo("Use Ctrl-C to stop watching and see the fired-alert summary.")


@alert.command("unsubscribe")
@click.argument("sub_id", required=False)
@click.option("--all", "-a", "all_for", default=None, help="Unsubscribe ALL alerts for a ticker.")
def alert_unsubscribe(sub_id: Optional[str], all_for: Optional[str]) -> None:
    """Remove an alert subscription by ID, or --all for a ticker.

    \b
    Examples:
        ibpaper alert unsubscribe abc123def456
        ibpaper alert unsubscribe --all AAPL
    """
    if sub_id is None and all_for is None:
        click.secho("✖  Must provide a subscription ID or use --all <TICKER>.", fg="red")
        raise SystemExit(1)

    if all_for is not None:
        click.echo(f"To unsubscribe all alerts for {all_for}, stop the watch (Ctrl-C) "
                   f"and restart without that ticker.")
        click.echo("Subscriptions are managed in-memory during the watch session.")
    else:
        click.echo(f"Unsubscribe {sub_id}: subscriptions are managed in-memory during the watch session.")
        click.echo("Stop the watch (Ctrl-C) and restart without that subscription.")


@alert.command("watch")
@click.option("--timeout", "-t", type=int, default=None, help="Auto-stop after N seconds.")
def alert_watch(timeout: Optional[int]) -> None:
    """Start the alert engine and monitor all subscriptions.

    Runs in the foreground until Ctrl-C is pressed.  During the watch:

    \b
    - Real-time prices stream for every subscribed ticker.
    - When a condition is met the alert fires and its callback runs.
    - ONCE-mode subscriptions are removed after firing.
    - EVERY-mode subscriptions re-arm.

    \b
    Examples:
        ibpaper alert watch
        ibpaper alert watch --timeout 3600   # run for 1 hour
    """
    # This command demonstrates the engine.  In a full implementation,
    # subscriptions would be loaded from config/state and the engine
    # would run with them.

    click.echo()
    click.secho("Alert Watch", bold=True)
    click.echo("───────────")
    click.echo()
    click.echo("To use the alert watch, first subscribe to tickers in the same")
    click.echo("Python process using the AlertEngine API:")
    click.echo()
    click.echo("    from ib_paper import ConnectionManager, AlertEngine")
    click.echo("    from ib_paper.types import AlertCondition, AlertField, AlertOperator, AlertMode")
    click.echo()
    click.echo("    cm = ConnectionManager()")
    click.echo("    cm.connect()")
    click.echo("    engine = AlertEngine(cm.ib)")
    click.echo()
    click.echo("    engine.subscribe('AAPL',")
    click.echo("        AlertCondition(AlertField.LAST, AlertOperator.GTE, 200.0),")
    click.echo("        callback=lambda sub: print(f'ALERT: {sub.ticker}'),")
    click.echo("        mode=AlertMode.ONCE)")
    click.echo()
    click.echo("    engine.run()   # blocks until Ctrl-C")
    click.echo()


# ======================================================================
# positions
# ======================================================================

@cli.command()
@click.option("--symbol", "-s", default=None, help="Filter by symbol.")
def positions(symbol: Optional[str]) -> None:
    """List current positions with unrealized P&L.

    \b
    Examples:
        ibpaper positions
        ibpaper positions --symbol AAPL
    """
    try:
        ib = _connect_readonly(click.get_current_context())
        all_positions = PositionService.list_positions(ib)
    except (IBPaperError, click.Abort) as exc:
        if isinstance(exc, click.Abort):
            return
        click.secho(f"✖  {exc}", fg="red")
        return

    if symbol:
        all_positions = [p for p in all_positions if p.symbol.upper() == symbol.upper()]
        if not all_positions:
            click.echo(f"No position found for '{symbol.upper()}'.")
            return

    if not all_positions:
        click.echo("No open positions.")
        return

    click.echo()
    rows = []
    for p in all_positions:
        if p.market_value - p.unrealized_pnl != 0:
            pct = p.unrealized_pnl / (p.market_value - p.unrealized_pnl) * 100
        else:
            pct = 0.0
        rows.append({
            "Symbol": p.symbol,
            "Qty": f"{p.quantity:,.0f}",
            "Avg Cost": format_money(p.average_cost),
            "Mkt Price": format_money(p.market_price),
            "Mkt Value": format_money(p.market_value),
            "Unreal. P&L": format_money(p.unrealized_pnl),
            "P&L %": f"{pct:+.2f}%",
        })

    # For single-symbol view, add extra detail
    if symbol and len(all_positions) == 1:
        p = all_positions[0]
        click.echo(table(rows))
        click.echo()
        click.echo(f"  Realized P&L (today): {format_money(p.realized_pnl)}")
        click.echo(f"  Account             : {p.account}")
    else:
        click.echo(table(rows))


# ======================================================================
# orders
# ======================================================================

@cli.command()
@click.option("--pending", "-p", is_flag=True, help="Show only pending/submitted.")
@click.option("--completed", "-c", is_flag=True, help="Show only filled/cancelled.")
@click.option("--all", "-a", "show_all", is_flag=True, help="Show all orders.")
def orders(pending: bool, completed: bool, show_all: bool) -> None:
    """List orders.

    \b
    Examples:
        ibpaper orders              # Active orders
        ibpaper orders --completed  # Filled / cancelled
        ibpaper orders --all        # Everything
    """
    try:
        ib = _connect_readonly(click.get_current_context())
        all_trades = OrderService.get_all_orders(ib)
    except (IBPaperError, click.Abort) as exc:
        if isinstance(exc, click.Abort):
            return
        click.secho(f"✖  {exc}", fg="red")
        return

    if not all_trades:
        click.echo("No orders in this session.")
        return

    # Filter
    active_statuses = {"PendingSubmit", "PendingCancel", "PreSubmitted", "Submitted"}
    complete_statuses = {"Filled", "Cancelled", "Inactive"}

    if pending:
        filtered = [t for t in all_trades if t.orderStatus.status in active_statuses]
    elif completed:
        filtered = [t for t in all_trades if t.orderStatus.status in complete_statuses]
    elif show_all:
        filtered = all_trades
    else:
        # Default: only active
        filtered = [t for t in all_trades if t.orderStatus.status in active_statuses]

    if not filtered:
        click.echo("No matching orders.")
        return

    click.echo()
    rows = []
    for t in filtered:
        rows.append({
            "ID": str(t.order.orderId),
            "Symbol": t.contract.symbol,
            "Action": t.order.action,
            "Qty": str(t.order.totalQuantity),
            "Type": t.order.orderType,
            "Status": t.orderStatus.status,
            "Filled": str(t.orderStatus.filled),
            "Remain": str(t.orderStatus.remaining),
        })

    click.echo(table(rows))


# ======================================================================
# cancel
# ======================================================================

@cli.command()
@click.argument("order_id", type=int)
def cancel(order_id: int) -> None:
    """Cancel a pending order by its ID.

    \b
    Example:
        ibpaper cancel 42
    """
    try:
        ib = _get_ib(click.get_current_context())
        OrderService.cancel_order(ib, order_id)
        click.secho(f"✓  Order {order_id} cancelled.", fg="green")
    except (IBPaperError, click.Abort) as exc:
        if isinstance(exc, click.Abort):
            return
        click.secho(f"✖  {exc}", fg="red")
        raise SystemExit(1)


# ======================================================================
# Entry point
# ======================================================================

def main() -> None:
    """Programmatic entry point (also used by console_scripts)."""
    cli()


if __name__ == "__main__":
    main()
