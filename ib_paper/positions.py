"""Position listing and management."""

from typing import Optional

from ib_insync import IB, Trade

from .account import AccountService
from .exceptions import OrderError
from .orders import OrderService
from .types import OrderAction, OrderRequest, OrderType, PositionInfo


class PositionService:
    """Static methods for viewing and closing positions."""

    @staticmethod
    def list_positions(ib: IB) -> list[PositionInfo]:
        """Return all open positions."""
        return AccountService.get_portfolio(ib)

    @staticmethod
    def get_position(ib: IB, symbol: str) -> Optional[PositionInfo]:
        """Return a single position by symbol, or None."""
        return AccountService.get_position(ib, symbol)

    @staticmethod
    def close_position(
        ib: IB,
        symbol: str,
        qty: Optional[int] = None,
    ) -> Trade:
        """Close all or part of a position.

        Args:
            ib: Connected IB instance.
            symbol: Ticker symbol.
            qty: Number of shares to sell.  If ``None``, the entire position
                is closed.

        Returns:
            The ``Trade`` object for the closing order.

        Raises:
            OrderError: If no position exists for *symbol* or the position
                quantity is less than *qty*.
        """
        pos = AccountService.get_position(ib, symbol)
        if pos is None:
            raise OrderError(
                f"No position found for '{symbol}'. Nothing to close."
            )

        if qty is None:
            qty = int(abs(pos.quantity))
        else:
            if qty > abs(pos.quantity):
                raise OrderError(
                    f"Cannot close {qty} shares of '{symbol}' -- "
                    f"only {abs(pos.quantity)} shares held."
                )

        # If the position is short (negative qty), we need to BUY to close.
        action = OrderAction.SELL if pos.quantity > 0 else OrderAction.BUY

        request = OrderRequest(
            symbol=symbol.upper(),
            action=action,
            total_quantity=qty,
            order_type=OrderType.MKT,
        )
        return OrderService.place_order(ib, request)

    @staticmethod
    def close_all_positions(ib: IB) -> list[Trade]:
        """Close every open position at market.

        Returns a list of ``Trade`` objects, one per position closed.
        """
        trades: list[Trade] = []
        errors: list[str] = []

        for pos in PositionService.list_positions(ib):
            try:
                trade = PositionService.close_position(ib, pos.symbol)
                trades.append(trade)
            except OrderError as exc:
                errors.append(str(exc))

        if errors and not trades:
            raise OrderError("\n".join(errors))

        return trades
