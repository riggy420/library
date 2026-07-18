"""Account queries -- summary, portfolio, P&L."""

from typing import Optional

from ib_insync import IB

from .types import AccountSnapshot, PositionInfo
from .exceptions import ConnectionError


class AccountService:
    """Static methods for querying account information from TWS / IB Gateway.

    All methods receive an ``ib_insync.IB`` instance as their first argument
    (dependency injection) so they are trivially testable.
    """

    @staticmethod
    def get_summary(ib: IB) -> AccountSnapshot:
        """Fetch key account metrics from TWS.

        Returns an ``AccountSnapshot`` dataclass.
        """
        # ib.accountSummary() returns a list of AccountValue named tuples.
        # Each has .account, .tag, .value, .currency fields.
        try:
            items = ib.accountSummary()
        except Exception as exc:
            raise ConnectionError(f"Could not fetch account summary: {exc}") from exc

        snapshot = AccountSnapshot()
        for item in items:
            try:
                val = float(item.value)
            except (ValueError, TypeError):
                continue

            tag = item.tag
            if tag == "NetLiquidation":
                snapshot.net_liquidation = val
            elif tag == "TotalCashValue":
                snapshot.total_cash = val
            elif tag == "BuyingPower":
                snapshot.buying_power = val
            elif tag == "GrossPnL":
                snapshot.gross_pnl = val
            elif tag == "RealizedPnL":
                snapshot.realized_pnl = val
            elif tag == "UnrealizedPnL":
                snapshot.unrealized_pnl = val
            elif tag == "AvailableFunds":
                snapshot.available_funds = val
            if item.currency:
                snapshot.currency = item.currency
        return snapshot

    @staticmethod
    def get_portfolio(ib: IB) -> list[PositionInfo]:
        """Return all portfolio positions as ``PositionInfo`` objects."""
        try:
            raw = ib.portfolio()
        except Exception as exc:
            raise ConnectionError(f"Could not fetch portfolio: {exc}") from exc

        positions: list[PositionInfo] = []
        for pos in raw:
            positions.append(
                PositionInfo(
                    symbol=pos.contract.symbol,
                    quantity=float(pos.position),
                    average_cost=float(pos.averageCost),
                    market_price=float(pos.marketPrice),
                    market_value=float(pos.marketValue),
                    unrealized_pnl=float(pos.unrealizedPNL),
                    realized_pnl=float(pos.realizedPNL),
                    account=pos.account,
                )
            )
        return positions

    @staticmethod
    def get_position(ib: IB, symbol: str) -> Optional[PositionInfo]:
        """Return a single position by *symbol* (case-insensitive), or None."""
        for pos in AccountService.get_portfolio(ib):
            if pos.symbol.upper() == symbol.upper():
                return pos
        return None

    @staticmethod
    def display_summary(ib: IB) -> str:
        """Return a human-readable multi-line summary string."""
        s = AccountService.get_summary(ib)
        lines = [
            "Account Summary",
            "───────────────",
            f"  Net Liquidation : {s.net_liquidation:>12,.2f} {s.currency}",
            f"  Total Cash      : {s.total_cash:>12,.2f} {s.currency}",
            f"  Buying Power    : {s.buying_power:>12,.2f} {s.currency}",
            f"  Available Funds : {s.available_funds:>12,.2f} {s.currency}",
            "",
            f"  Gross P&L       : {s.gross_pnl:>12,.2f} {s.currency}",
            f"  Realized P&L    : {s.realized_pnl:>12,.2f} {s.currency}",
            f"  Unrealized P&L  : {s.unrealized_pnl:>12,.2f} {s.currency}",
        ]
        return "\n".join(lines)
