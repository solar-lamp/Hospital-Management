import pytest

from database import read_connection, transaction
from services import (admission_service, auth_service, billing_service, patient_service,
                      pharmacy_service, report_service, staff_service)
from services.auth_service import AuthError
from utils.permissions import PermissionDenied
from utils.validators import ValidationError


def test_passwords_are_hashed(admin):
    with read_connection() as conn:
        stored = conn.execute("SELECT password_hash FROM users").fetchone()[0]
    assert "Admin@123" not in stored and stored.startswith("pbkdf2_sha256$")
    assert auth_service.verify_password("Admin@123", stored)
    assert not auth_service.verify_password("admin@123", stored)


def test_login_success_and_failures(admin):
    assert auth_service.authenticate("ADMIN", "Admin@123")["role"] == "ADMIN"
    with pytest.raises(AuthError):
        auth_service.authenticate("admin", "wrong")
    with pytest.raises(AuthError):
        auth_service.authenticate("ghost", "Admin@123")


def test_deactivated_account_cannot_log_in(admin, make_user):
    clerk = make_user("BILLING")
    auth_service.update_user(admin, clerk["user_id"], clerk["full_name"], "BILLING", None, False)
    with pytest.raises(AuthError, match="deactivated"):
        auth_service.authenticate(clerk["username"], "Passw0rd!")


def test_first_admin_only_once(admin):
    with pytest.raises(AuthError):
        auth_service.create_first_admin("second", "Second", "Admin@123")


def test_weak_password_and_duplicate_username(admin):
    with pytest.raises(ValidationError, match="8 characters"):
        auth_service.create_user(admin, "newbie", "New", "short1", "NURSE")
    with pytest.raises(ValidationError, match="already taken"):
        auth_service.create_user(admin, "Admin", "Dup", "Passw0rd!", "NURSE")


def test_last_admin_protected(admin):
    with pytest.raises(ValidationError):
        auth_service.update_user(admin, admin["user_id"], "Me", "NURSE", None, True)


@pytest.mark.parametrize("role, call", [
    ("PHARMACIST", lambda u, ctx: patient_service.register(u, {"full_name": "X"})),
    ("RECEPTIONIST", lambda u, ctx: pharmacy_service.save_medicine(u, {"name": "X"})),
    ("NURSE", lambda u, ctx: billing_service.search(u)),
    ("BILLING", lambda u, ctx: staff_service.create(u, {"full_name": "X", "role": "NURSE"})),
    ("DOCTOR", lambda u, ctx: admission_service.add_ward(u, "W")),
    ("NURSE", lambda u, ctx: auth_service.create_user(u, "abc", "A", "Passw0rd!", "ADMIN")),
    ("RECEPTIONIST", lambda u, ctx: report_service.run_report(
        u, "bills", ctx["d"], ctx["d"])),
])
def test_t17_unauthorized_operations_denied(make_user, role, call):
    from datetime import date
    with pytest.raises(PermissionDenied):
        call(make_user(role), {"d": date.today()})


def test_inactive_user_has_no_permissions(admin):
    with pytest.raises(PermissionDenied):
        patient_service.search({**admin, "active": 0})


def test_audit_log_is_append_only(admin, patient):
    import sqlite3
    with read_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0] >= 2
    with pytest.raises(sqlite3.IntegrityError):
        with transaction() as conn:
            conn.execute("DELETE FROM audit_logs")
    with pytest.raises(sqlite3.IntegrityError):
        with transaction() as conn:
            conn.execute("UPDATE audit_logs SET action = 'X'")
