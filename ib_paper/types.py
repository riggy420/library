"""Enumerations and dataclasses for ib_paper."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class OrderAction(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MKT = "MKT"
    LMT = "LMT"
    STP = "STP"
    STP_LMT = "STP LMT"


class OrderStatus(Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    CANCELLED = "cancelled"


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"


@dataclass
class OrderRequest:
    """User-facing order request before IB contract resolution."""

    symbol: str
    action: OrderAction
    total_quantity: int
    order_type: OrderType = OrderType.MKT
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    currency: str = "USD"
    exchange: str = "SMART"
    sec_type: str = "STK"


@dataclass
class PositionInfo:
    """Flattened position data for display."""

    symbol: str
    quantity: float
    average_cost: float
    market_price: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float
    account: str = ""


class AlertField(Enum):
    """Which price field to watch."""
    LAST = "last"
    BID = "bid"
    ASK = "ask"
    CLOSE = "close"


class AlertOperator(Enum):
    """Comparison operator for an alert condition.

    CROSS fires once when the price crosses the threshold in **either**
    direction — upward (was below, now >=) or downward (was above, now <=).
    """
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    EQ = "=="
    CROSS = "cross"


class AlertMode(Enum):
    """Firing behaviour."""
    ONCE = "once"     # fire once, then auto-unsubscribe
    EVERY = "every"   # re-arm after every fire


@dataclass
class AlertCondition:
    """A single price-threshold condition.

    Example:
        AlertCondition(AlertField.LAST, AlertOperator.CROSS, 200.0)
        → "trigger when last price crosses $200 (either direction)"
    """
    field: AlertField
    operator: AlertOperator
    threshold: float

    def evaluate(self, price: float) -> bool:
        """Stateless check — does *price* satisfy the threshold right now?

        For ``CROSS`` this always returns ``False`` because crossing
        requires a previous price to compare against.  Use
        :meth:`AlertEngine._check_cross` instead for stateful crossing
        detection.
        """
        op = self.operator
        if op == AlertOperator.GT:
            return price > self.threshold
        elif op == AlertOperator.LT:
            return price < self.threshold
        elif op == AlertOperator.GTE:
            return price >= self.threshold
        elif op == AlertOperator.LTE:
            return price <= self.threshold
        elif op == AlertOperator.EQ:
            return price == self.threshold
        elif op == AlertOperator.CROSS:
            return False  # stateless — crossing handled by engine
        return False

    def describe(self) -> str:
        if self.operator == AlertOperator.CROSS:
            return f"{self.field.value} crosses {self.threshold}"
        return f"{self.field.value} {self.operator.value} {self.threshold}"


@dataclass
class Subscription:
    """A live alert subscription.

    Created by :meth:`AlertEngine.subscribe`, removed by :meth:`AlertEngine.unsubscribe`.
    """
    id: str
    ticker: str
    condition: AlertCondition
    mode: AlertMode = AlertMode.ONCE
    created_at: str = ""
    fired_at: str | None = None
    fire_price: float | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class AccountSnapshot:
    """Key account metrics."""

    net_liquidation: float = 0.0
    total_cash: float = 0.0
    buying_power: float = 0.0
    gross_pnl: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    available_funds: float = 0.0
    currency: str = "USD"
