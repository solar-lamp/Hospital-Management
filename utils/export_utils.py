"""Safe CSV / Excel export of report data frames."""

import io

import pandas as pd

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def neutralize(value):
    """Prefix text that a spreadsheet would treat as a formula."""
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def sanitize(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    out = df[columns].copy() if columns else df.copy()
    for col in out.columns:
        if out[col].dtype == object or pd.api.types.is_string_dtype(out[col]):
            out[col] = out[col].map(neutralize)
    return out


def to_csv_bytes(df: pd.DataFrame, columns: list[str] | None = None) -> bytes:
    return sanitize(df, columns).to_csv(index=False).encode("utf-8-sig")


def to_excel_bytes(df: pd.DataFrame, columns: list[str] | None = None,
                   sheet_name: str = "Report") -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        sanitize(df, columns).to_excel(writer, index=False, sheet_name=sheet_name[:31])
    return buffer.getvalue()
