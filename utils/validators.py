"""Reusable validation. Each function returns the cleaned value or raises
:class:`ValidationError` with a message suitable for showing to the user."""

import re
from datetime import date

from utils import clock


class ValidationError(ValueError):
    """Input failed a business or format rule."""


# Documented phone rule: optional leading '+', then 10 to 15 digits. Spaces
# and hyphens are allowed for readability and stripped before storage.
PHONE_RE = re.compile(r"^\+?\d{10,15}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


def clean_text(value, *, max_len: int = 200) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    if len(text) > max_len:
        raise ValidationError(f"Text must be at most {max_len} characters.")
    return text or None


def required_text(value, field: str, *, max_len: int = 200) -> str:
    text = clean_text(value, max_len=max_len)
    if not text:
        raise ValidationError(f"{field} is required.")
    return text


def phone(value, *, required: bool = False) -> str | None:
    text = clean_text(value, max_len=25)
    if not text:
        if required:
            raise ValidationError("Phone number is required.")
        return None
    digits = re.sub(r"[\s-]", "", text)
    if not PHONE_RE.match(digits):
        raise ValidationError(
            "Phone must contain 10 to 15 digits (optional leading +).")
    return digits


def email(value) -> str | None:
    text = clean_text(value, max_len=120)
    if not text:
        return None
    if not EMAIL_RE.match(text):
        raise ValidationError("Email address is not valid.")
    return text.lower()


def past_or_today(value: date | None, field: str) -> date | None:
    if value is None:
        return None
    if value > clock.today():
        raise ValidationError(f"{field} cannot be in the future.")
    return value


def date_of_birth(value: date | None) -> date | None:
    value = past_or_today(value, "Date of birth")
    if value is not None and value.year < 1900:
        raise ValidationError("Date of birth must be after 1900.")
    return value


def choice(value, allowed, field: str):
    if value not in allowed:
        raise ValidationError(f"{field} must be one of: {', '.join(map(str, allowed))}.")
    return value


def positive_int(value, field: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be a whole number.") from None
    if number != value and not isinstance(value, str):
        raise ValidationError(f"{field} must be a whole number.")
    if number <= 0:
        raise ValidationError(f"{field} must be greater than zero.")
    return number


def non_negative_int(value, field: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be a whole number.") from None
    if number < 0:
        raise ValidationError(f"{field} cannot be negative.")
    return number


def money_minor(value, field: str, *, allow_zero: bool = True) -> int:
    """Validate an amount already converted to integer minor units (paise)."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"{field} must be an amount in paise.")
    if value < 0 or (value == 0 and not allow_zero):
        raise ValidationError(
            f"{field} must be {'zero or more' if allow_zero else 'greater than zero'}.")
    return value


def username(value) -> str:
    text = (value or "").strip()
    if not USERNAME_RE.match(text):
        raise ValidationError(
            "Username must be 3-32 characters: letters, digits, '.', '_' or '-'.")
    return text.lower()


def password(value) -> str:
    if not value or len(value) < 8:
        raise ValidationError("Password must be at least 8 characters.")
    if value.isdigit() or value.isalpha():
        raise ValidationError("Password must mix letters with digits or symbols.")
    return value
