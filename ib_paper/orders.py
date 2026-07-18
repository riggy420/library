"""Order construction, placement, and cancellation."""

from typing import Optional

from ib_insync import IB, Stock, Trade, Order as IBOrder
from ib_insync import MarketOrder, LimitOrder, StopOrder, StopLimitOrder

from .exceptions import OrderError, ValidationError
from .types import OrderAction, OrderRequest, OrderType as OT


class OrderService:
    """Static methods for building and placing orders.

    All methods receive an ``ib_insync.IB`` instance as their first argument.
    """

    # ------------------------------------------------------------------
    # Contract resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_contract(
        ib: IB,
        symbol: str,
        sec_type: str = "STK",
        currency: str = "USD",
        exchange: str = "SMART",
    ) -> Stock:
        """Resolve *symbol* to a qualified IB ``Stock`` contract."""
        contract = Stock(symbol, exchange, currency)
        # ib_insync >=0.9.75: qualifyContracts returns a list
        try:
            qualified = ib.qualifyContracts(contract)
        except Exception as exc:
            raise OrderError(
                f"Symbol '{symbol}' could not be resolved. "
                f"Check the ticker and try again.\nDetails: {exc}"
            ) from exc

        if not qualified:
            raise OrderError(
                f"Symbol '{symbol}' could not be resolved. "
                "Check the ticker and try again."
            )
        return qualified[0]

    # ------------------------------------------------------------------
    # Order building
    # ------------------------------------------------------------------

    @staticmethod
    def _build_ib_order(request: OrderRequest) -> IBOrder:
        """Map an ``OrderRequest`` to the correct ``ib_insync`` order type."""
        action = request.action.value
        qty = request.total_quantity

        if request.order_type == OT.MKT:
            return MarketOrder(action, qty)
        elif request.order_type == OT.LMT:
            if request.limit_price is None:
                raise ValidationError("Limit price is required for LMT orders.")
            return LimitOrder(action, qty, request.limit_price)
        elif request.order_type == OT.STP:
            if request.stop_price is None:
                raise ValidationError("Stop price is required for STP orders.")
            return StopOrder(action, qty, request.stop_price)
        elif request.order_type == OT.STP_LMT:
            if request.stop_price is None or request.limit_price is None:
                raise ValidationError(
                    "Both stop and limit prices are required for STP LMT orders."
                )
            return StopLimitOrder(
                action, qty, request.limit_price, request.stop_price
            )
        else:
            raise ValidationError(f"Unknown order type: {request.order_type}")

    # ------------------------------------------------------------------
    # Placement
    # ------------------------------------------------------------------

    @staticmethod
    def place_order(ib: IB, request: OrderRequest) -> Trade:
        """Resolve the contract, build the order, and submit it to TWS.

        Returns an ``ib_insync.Trade`` object which carries ``orderStatus``,
        ``fills``, and events.
        """
        contract = OrderService._resolve_contract(
            ib,
            request.symbol,
            request.sec_type,
            request.currency,
            request.exchange,
        )
        order = OrderService._build_ib_order(request)

        try:
            trade = ib.placeOrder(contract, order)
        except Exception as exc:
            raise OrderError(
                f"Order for '{request.symbol}' was rejected.\n"
                f"Check price, quantity, and account permissions.\n"
                f"Details: {exc}"
            ) from exc

        return trade

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    @staticmethod
    def cancel_order(ib: IB, order_id: int) -> None:
        """Cancel a pending order by its IB order ID."""
        for trade in ib.trades():
            if trade.order.orderId == order_id:
                try:
                    ib.cancelOrder(trade.order)
                    return
                except Exception as exc:
                    raise OrderError(
                        f"Could not cancel order {order_id}: {exc}"
                    ) from exc
        raise OrderError(f"No pending order found with ID {order_id}.")

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @staticmethod
    def get_all_orders(ib: IB) -> list[Trade]:
        """Return all trades/orders known to this session."""
        return list(ib.trades())

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @classmethod
    def buy_market(cls, ib: IB, symbol: str, qty: int) -> Trade:
        """Place a market buy order."""
        return cls.place_order(
            ib,
            OrderRequest(
                symbol=symbol,
                action=OrderAction.BUY,
                total_quantity=qty,
                order_type=OT.MKT,
            ),
        )

    @classmethod
    def sell_market(cls, ib: IB, symbol: str, qty: int) -> Trade:
        """Place a market sell order."""
        return cls.place_order(
            ib,
            OrderRequest(
                symbol=symbol,
                action=OrderAction.SELL,
                total_quantity=qty,
                order_type=OT.MKT,
            ),
        )
