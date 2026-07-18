"""Custom exception hierarchy for ib_paper."""


class IBPaperError(Exception):
    """Base exception for all ib_paper errors."""


class ConnectionError(IBPaperError):
    """Failed to connect to TWS/IB Gateway."""


class ConfigError(IBPaperError):
    """Configuration is missing or invalid."""


class OrderError(IBPaperError):
    """Order placement, modification, or cancellation failed."""


class ValidationError(IBPaperError):
    """User input validation failed."""


class LiveAccountWarning(IBPaperError):
    """Raised when user appears to be connecting to a live (non-paper) account.

    This is a warning-level exception -- callers may catch it to prompt
    for confirmation before proceeding.
    """
