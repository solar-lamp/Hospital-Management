"""Centralized role-based permissions.

Pages use :func:`has_permission` to decide what to show, but every protected
service function calls :func:`require` itself, so hiding a menu item is never
the only safeguard.
"""

ROLES = ("ADMIN", "RECEPTIONIST", "DOCTOR", "NURSE", "PHARMACIST", "BILLING")

ROLE_LABELS = {
    "ADMIN": "Administrator",
    "RECEPTIONIST": "Receptionist",
    "DOCTOR": "Doctor",
    "NURSE": "Nurse",
    "PHARMACIST": "Pharmacist",
    "BILLING": "Billing staff",
}

PERMISSIONS: dict[str, set[str]] = {
    "dashboard.view": set(ROLES),
    "patients.view": {"ADMIN", "RECEPTIONIST", "DOCTOR", "NURSE", "BILLING"},
    "patients.edit": {"ADMIN", "RECEPTIONIST"},
    "staff.view": {"ADMIN", "RECEPTIONIST"},
    "staff.edit": {"ADMIN"},
    "attendance.edit": {"ADMIN"},
    "appointments.view": {"ADMIN", "RECEPTIONIST", "DOCTOR"},
    "appointments.edit": {"ADMIN", "RECEPTIONIST"},
    # Doctors may update the status of their own appointments only.
    "appointments.status": {"ADMIN", "RECEPTIONIST", "DOCTOR"},
    "admissions.view": {"ADMIN", "RECEPTIONIST", "DOCTOR", "NURSE"},
    "admissions.edit": {"ADMIN", "RECEPTIONIST"},
    "wards.manage": {"ADMIN"},
    "pharmacy.view": {"ADMIN", "PHARMACIST"},
    "pharmacy.edit": {"ADMIN", "PHARMACIST"},
    "suppliers.view": {"ADMIN", "PHARMACIST"},
    "suppliers.edit": {"ADMIN", "PHARMACIST"},
    "billing.view": {"ADMIN", "BILLING"},
    "billing.edit": {"ADMIN", "BILLING"},
    "reports.view": {"ADMIN", "RECEPTIONIST", "PHARMACIST", "BILLING"},
    "users.manage": {"ADMIN"},
    "audit.view": {"ADMIN"},
    "system.backup": {"ADMIN"},
}


class PermissionDenied(Exception):
    """Raised when the current user may not perform an operation."""


def has_permission(user, permission: str) -> bool:
    if user is None or not user.get("active", True):
        return False
    return user.get("role") in PERMISSIONS.get(permission, set())


def require(user, permission: str) -> None:
    if not has_permission(user, permission):
        role = ROLE_LABELS.get((user or {}).get("role"), "This account")
        raise PermissionDenied(f"{role} is not allowed to perform '{permission}'.")
