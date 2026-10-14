"""Money and display formatting.

Money is stored as integer minor units (paise) to avoid binary floating-point
errors. Conversion from user input goes through Decimal.
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import config
from utils.validators import ValidationError


def to_minor(amount) -> int:
    """Convert a rupee amount (str/int/float/Decimal) to paise."""
    try:
        value = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise ValidationError(f"'{amount}' is not a valid amount.") from None
    return int(value * 100)


def from_minor(minor: int | None) -> Decimal:
    return (Decimal(minor or 0) / 100).quantize(Decimal("0.01"))


def money(minor: int | None) -> str:
    value = from_minor(minor)
    sign = "-" if value < 0 else ""
    return f"{sign}{config.CURRENCY_SYMBOL}{abs(value):,.2f}"


def percent_of(minor: int, basis_points: int) -> int:
    """Return ``minor * basis_points / 10000`` rounded half-up, in integers."""
    return (minor * basis_points + 5000) // 10000


def label(code: str | None) -> str:
    """'NO_SHOW' -> 'No show'. Missing values (None/NaN) become ''."""
    if not isinstance(code, str) or not code:
        return ""
    return code.replace("_", " ").capitalize()
