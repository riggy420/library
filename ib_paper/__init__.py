"""
ib_paper -- Interactive Brokers Paper Trading CLI and Library.

Provides a programmatic API and a command-line interface for paper trading
through Interactive Brokers TWS or IB Gateway.

Usage:
    from ib_paper import ConnectionManager, AccountService, OrderService

    cm = ConnectionManager()
    cm.connect()
    ib = cm.ib
    snapshot = AccountService.get_summary(ib)
    cm.disconnect()
"""

__version__ = "0.1.0"
__author__ = "Ricky"

from .connection import ConnectionManager
from .account import AccountService
from .orders import OrderService
from .positions import PositionService
from .config import Config
from .exceptions import IBPaperError, ConnectionError, ConfigError, OrderError
from .types import OrderAction, OrderType, OrderStatus, ConnectionState, OrderRequest, PositionInfo, AccountSnapshot

__all__ = [
    "ConnectionManager",
    "AccountService",
    "OrderService",
    "PositionService",
    "Config",
    "IBPaperError",
    "ConnectionError",
    "ConfigError",
    "OrderError",
    "OrderAction",
    "OrderType",
    "OrderStatus",
    "ConnectionState",
    "OrderRequest",
    "PositionInfo",
    "AccountSnapshot",
]
