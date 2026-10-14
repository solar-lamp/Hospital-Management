from repositories.common import many
from utils import clock


def insert(conn, user_id, action, entity_type, entity_id=None, description=None):
    conn.execute(
        "INSERT INTO audit_logs (user_id, action, entity_type, entity_id, description, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, action, entity_type, entity_id, description, clock.ts()),
    )


def recent(conn, limit=200, entity_type=None):
    sql = ("SELECT a.audit_id, a.created_at, u.username, a.action, a.entity_type,"
           " a.entity_id, a.description FROM audit_logs a"
           " LEFT JOIN users u ON u.user_id = a.user_id")
    params: list = []
    if entity_type:
        sql += " WHERE a.entity_type = ?"
        params.append(entity_type)
    sql += " ORDER BY a.audit_id DESC LIMIT ?"
    params.append(limit)
    return many(conn, sql, params)
