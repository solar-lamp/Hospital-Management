"""Authentication and user administration.

Passwords are hashed with PBKDF2-HMAC-SHA256 (Python standard library) using a
random 16-byte salt and a high iteration count. A maintained standard-library
algorithm is used instead of argon2/bcrypt so the identical code also runs in
the browser build (Pyodide), where those C extensions are not guaranteed.
"""

import base64
import hashlib
import hmac
import secrets

import config
from database import read_connection, transaction
from repositories import user_repository
from services import audit_service
from utils import validators as v
from utils.permissions import ROLES, require

ALGORITHM = "pbkdf2_sha256"


class AuthError(Exception):
    """Invalid credentials or inactive account."""


def hash_password(password: str, iterations: int | None = None) -> str:
    iterations = iterations or config.pbkdf2_iterations()
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return "$".join([ALGORITHM, str(iterations), base64.b64encode(salt).decode(),
                     base64.b64encode(digest).decode()])


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, digest = stored.split("$")
        if algorithm != ALGORITHM:
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt),
                                     int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# A fixed dummy hash keeps the response time similar for unknown usernames.
_DUMMY_HASH = None


def authenticate(username: str, password: str) -> dict:
    global _DUMMY_HASH
    username = (username or "").strip().lower()
    with read_connection() as conn:
        row = user_repository.get_by_username(conn, username)
    if row is None:
        _DUMMY_HASH = _DUMMY_HASH or hash_password("dummy-password-1")
        verify_password(password or "", _DUMMY_HASH)
        raise AuthError("Invalid username or password.")
    if not verify_password(password or "", row["password_hash"]):
        raise AuthError("Invalid username or password.")
    if not row["active"]:
        raise AuthError("This account has been deactivated. Contact an administrator.")
    with transaction() as conn:
        user_repository.touch_login(conn, row["user_id"])
        audit_service.log(conn, row, "LOGIN", "user", row["user_id"])
    return load_user(row["user_id"])


def load_user(user_id: int) -> dict | None:
    """Fresh copy from the database on every page run, so deactivation and
    role changes take effect immediately."""
    with read_connection() as conn:
        return user_repository.get(conn, user_id)


def has_users() -> bool:
    with read_connection() as conn:
        return user_repository.count(conn) > 0


def _validate_user(data: dict) -> dict:
    return {
        "full_name": v.required_text(data.get("full_name"), "Full name", max_len=100),
        "role": v.choice(data.get("role"), ROLES, "Role"),
        "staff_id": data.get("staff_id") or None,
    }


def create_first_admin(username, full_name, password) -> int:
    """Bootstrap: only allowed while the users table is empty."""
    username = v.username(username)
    full_name = v.required_text(full_name, "Full name", max_len=100)
    password = v.password(password)
    with transaction() as conn:
        if user_repository.count(conn) > 0:
            raise AuthError("An administrator already exists.")
        user_id = user_repository.insert(conn, username, full_name, hash_password(password),
                                         "ADMIN", None)
        audit_service.log(conn, {"user_id": user_id}, "CREATE", "user", user_id,
                          "first administrator")
    return user_id


def create_user(actor, username, full_name, password, role, staff_id=None) -> int:
    require(actor, "users.manage")
    username = v.username(username)
    data = _validate_user({"full_name": full_name, "role": role, "staff_id": staff_id})
    password = v.password(password)
    with transaction() as conn:
        if user_repository.get_by_username(conn, username):
            raise v.ValidationError(f"Username '{username}' is already taken.")
        user_id = user_repository.insert(conn, username, data["full_name"],
                                         hash_password(password), data["role"], data["staff_id"])
        audit_service.log(conn, actor, "CREATE", "user", user_id, f"role {data['role']}")
    return user_id


def update_user(actor, user_id, full_name, role, staff_id, active):
    require(actor, "users.manage")
    data = _validate_user({"full_name": full_name, "role": role, "staff_id": staff_id})
    with transaction() as conn:
        existing = user_repository.get(conn, user_id)
        if existing is None:
            raise v.ValidationError("User not found.")
        if user_id == actor["user_id"] and (not active or data["role"] != "ADMIN"):
            raise v.ValidationError("You cannot deactivate or demote your own account.")
        if existing["role"] == "ADMIN" and existing["active"] and (
                not active or data["role"] != "ADMIN"):
            if user_repository.count_active_admins(conn) <= 1:
                raise v.ValidationError("At least one active administrator is required.")
        user_repository.update(conn, user_id, data["full_name"], data["role"],
                               data["staff_id"], active)
        audit_service.log(conn, actor, "UPDATE", "user", user_id,
                          f"role {data['role']}, active={bool(active)}")


def reset_password(actor, user_id, new_password):
    require(actor, "users.manage")
    new_password = v.password(new_password)
    with transaction() as conn:
        if user_repository.get(conn, user_id) is None:
            raise v.ValidationError("User not found.")
        user_repository.set_password(conn, user_id, hash_password(new_password))
        audit_service.log(conn, actor, "RESET_PASSWORD", "user", user_id)


def change_own_password(actor, current_password, new_password):
    with read_connection() as conn:
        row = user_repository.get_by_username(conn, actor["username"])
    if row is None or not verify_password(current_password or "", row["password_hash"]):
        raise AuthError("Current password is incorrect.")
    new_password = v.password(new_password)
    with transaction() as conn:
        user_repository.set_password(conn, actor["user_id"], hash_password(new_password))
        audit_service.log(conn, actor, "CHANGE_PASSWORD", "user", actor["user_id"])


def list_users(actor):
    require(actor, "users.manage")
    with read_connection() as conn:
        return user_repository.list_all(conn)


def log_logout(actor):
    with transaction() as conn:
        audit_service.log(conn, actor, "LOGOUT", "user", actor["user_id"])
