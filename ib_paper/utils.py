"""Shared formatting, validation, and display utilities."""

import sys
from typing import Any, Optional

from .exceptions import ValidationError


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_symbol(symbol: str) -> str:
    """Normalize and validate a ticker symbol.

    Returns the uppercased, stripped symbol.
    Raises ValidationError on empty or obviously invalid input.
    """
    if not symbol or not symbol.strip():
        raise ValidationError("Symbol must not be empty.")
    cleaned = symbol.strip().upper()
    if not cleaned.isascii() or len(cleaned) > 10:
        raise ValidationError(f"Symbol '{cleaned}' looks invalid (max 10 ASCII chars).")
    return cleaned


def validate_quantity(qty: int) -> int:
    """Validate that *qty* is a positive integer."""
    if qty <= 0:
        raise ValidationError(f"Quantity must be positive, got {qty}.")
    return qty


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_money(amount: float, currency: str = "USD") -> str:
    """Format a float as currency: $12,345.67."""
    sign = "$" if currency == "USD" else f"{currency} "
    return f"{sign}{amount:,.2f}"


def format_pnl(amount: float) -> str:
    """Format a P&L value with a leading sign."""
    if amount >= 0:
        return f"+{amount:,.2f}"
    return f"{amount:,.2f}"


def pnl_color(amount: float) -> Optional[str]:
    """Return 'green' / 'red' / None for ANSI colouring (only on TTY)."""
    if not sys.stdout.isatty():
        return None
    if amount > 0:
        return "green"
    if amount < 0:
        return "red"
    return None


def color_for(amount: float) -> Optional[str]:
    """Alias for pnl_color -- used internally by the CLI."""
    return pnl_color(amount)


# ---------------------------------------------------------------------------
# Table printer
# ---------------------------------------------------------------------------

def table(rows: list[dict[str, Any]], headers: Optional[list[str]] = None) -> str:
    """Render a list of dicts as a simple ASCII table.

    Column widths are auto-sized to fit the widest cell in each column.
    Headers are derived from the keys of the first row if not supplied.
    """
    if not rows:
        return "(no data)"

    if headers is None:
        headers = list(rows[0].keys())

    # Collect all values as strings
    string_rows: list[list[str]] = []
    for row in rows:
        string_rows.append([str(row.get(h, "")) for h in headers])

    # Compute column widths (header vs data)
    col_widths = [len(h) for h in headers]
    for srow in string_rows:
        for i, cell in enumerate(srow):
            col_widths[i] = max(col_widths[i], len(cell))

    def _fmt_row(cells: list[str]) -> str:
        parts = [c.ljust(col_widths[i]) for i, c in enumerate(cells)]
        return "  ".join(parts)

    lines = [_fmt_row(headers), "-" * (sum(col_widths) + 2 * (len(headers) - 1))]
    for srow in string_rows:
        lines.append(_fmt_row(srow))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Interactive helpers
# ---------------------------------------------------------------------------

def confirm(prompt: str, default: bool = False) -> bool:
    """Ask user for y/n confirmation.  Returns True on 'y'."""
    suffix = " [y/N] " if not default else " [Y/n] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    if default:
        return answer != "n"
    return answer == "y"


def is_paper_port(port: int) -> bool:
    """Return True if *port* is the standard paper trading port."""
    return port == 7497
