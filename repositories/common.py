"""Small helpers shared by repository modules."""

import sqlite3


def rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


def one(conn: sqlite3.Connection, sql: str, params=()) -> dict | None:
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def many(conn: sqlite3.Connection, sql: str, params=()) -> list[dict]:
    return rows_to_dicts(conn.execute(sql, params).fetchall())


def scalar(conn: sqlite3.Connection, sql: str, params=()):
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def like(term: str) -> str:
    """Escape LIKE wildcards in user input and wrap with %...%."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
