"""Append-only audit trail. Never store medical details or secrets here."""

from database import read_connection
from repositories import audit_repository
from utils.permissions import require


def log(conn, user, action, entity_type, entity_id=None, description=None):
    audit_repository.insert(conn, (user or {}).get("user_id"), action, entity_type,
                            entity_id, description)


def recent(user, limit=200, entity_type=None):
    require(user, "audit.view")
    with read_connection() as conn:
        return audit_repository.recent(conn, limit, entity_type)
