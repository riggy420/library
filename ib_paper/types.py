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
