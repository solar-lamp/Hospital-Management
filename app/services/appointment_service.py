from datetime import date, datetime

from database import read_connection, transaction
from repositories import appointment_repository, patient_repository, staff_repository
from services import audit_service
from utils import clock
from utils import validators as v
from utils.permissions import PermissionDenied, require

STATUSES = ("SCHEDULED", "CONFIRMED", "COMPLETED", "CANCELLED", "NO_SHOW")
# Allowed status transitions. Completed/cancelled/no-show are final.
TRANSITIONS = {
    "SCHEDULED": {"CONFIRMED", "COMPLETED", "CANCELLED", "NO_SHOW"},
    "CONFIRMED": {"COMPLETED", "CANCELLED", "NO_SHOW"},
}


def _validate_interval(start: datetime, end: datetime, *, allow_past: bool = False):
    if end <= start:
        raise v.ValidationError("Appointment end time must be after the start time.")
    if start.date() != end.date():
        raise v.ValidationError("An appointment must start and end on the same day.")
    if (end - start).total_seconds() > 4 * 3600:
        raise v.ValidationError("An appointment cannot be longer than 4 hours.")
    if not allow_past and start < clock.now():
        raise v.ValidationError("Appointments cannot be booked in the past.")


def _check_overlap(conn, doctor_id, start_at, end_at, exclude_id=None):
    overlaps = appointment_repository.find_overlaps(conn, doctor_id, start_at, end_at,
                                                    exclude_id)
    if overlaps:
        o = overlaps[0]
        raise v.ValidationError(
            f"The doctor already has an appointment from {o['start_at'][11:16]} to "
            f"{o['end_at'][11:16]} ({o['patient_name']}).")


def book(user, patient_id: int, doctor_id: int, start: datetime, end: datetime,
         reason: str | None = None, *, allow_past: bool = False) -> dict:
    require(user, "appointments.edit")
    _validate_interval(start, end, allow_past=allow_past)
    start_at, end_at = clock.ts(start), clock.ts(end)
    reason = v.clean_text(reason, max_len=200)
    with transaction() as conn:
        patient = patient_repository.get(conn, patient_id)
        if patient is None or patient["status"] != "ACTIVE":
            raise v.ValidationError("Select an existing, active patient.")
        doctor = staff_repository.get(conn, doctor_id)
        if doctor is None or doctor["role"] != "DOCTOR" or doctor["status"] != "ACTIVE":
            raise v.ValidationError("Select an existing, active doctor.")
        _check_overlap(conn, doctor_id, start_at, end_at)
        appointment_id = appointment_repository.insert(conn, patient_id, doctor_id, start_at,
                                                       end_at, reason, user["user_id"])
        audit_service.log(conn, user, "CREATE", "appointment", appointment_id)
        return appointment_repository.get(conn, appointment_id)


def _guard_doctor_scope(user, appointment):
    if user["role"] == "DOCTOR" and appointment["doctor_id"] != user.get("staff_id"):
        raise PermissionDenied("Doctors can only update their own appointments.")


def update_status(user, appointment_id: int, new_status: str):
    require(user, "appointments.status")
    v.choice(new_status, STATUSES, "Status")
    with transaction() as conn:
        appt = appointment_repository.get(conn, appointment_id)
        if appt is None:
            raise v.ValidationError("Appointment not found.")
        _guard_doctor_scope(user, appt)
        if new_status not in TRANSITIONS.get(appt["status"], set()):
            raise v.ValidationError(
                f"Cannot change an appointment from {appt['status']} to {new_status}.")
        if new_status in ("COMPLETED", "NO_SHOW") and appt["start_at"] > clock.ts():
            raise v.ValidationError("A future appointment cannot be marked completed/no-show.")
        appointment_repository.set_status(conn, appointment_id, new_status)
        audit_service.log(conn, user, "STATUS", "appointment", appointment_id, new_status)


def reschedule(user, appointment_id: int, start: datetime, end: datetime):
    require(user, "appointments.edit")
    _validate_interval(start, end)
    start_at, end_at = clock.ts(start), clock.ts(end)
    with transaction() as conn:
        appt = appointment_repository.get(conn, appointment_id)
        if appt is None:
            raise v.ValidationError("Appointment not found.")
        if appt["status"] not in TRANSITIONS:
            raise v.ValidationError("Only scheduled or confirmed appointments can be moved.")
        _check_overlap(conn, appt["doctor_id"], start_at, end_at, exclude_id=appointment_id)
        appointment_repository.reschedule(conn, appointment_id, start_at, end_at)
        audit_service.log(conn, user, "RESCHEDULE", "appointment", appointment_id)


def search(user, date_from: date | None = None, date_to: date | None = None, doctor_id=None,
           patient_id=None, status=None):
    require(user, "appointments.view")
    if user["role"] == "DOCTOR":
        doctor_id = user.get("staff_id") or -1  # doctors see only their own list
    with read_connection() as conn:
        return appointment_repository.search(
            conn, date_from.isoformat() if date_from else None,
            date_to.isoformat() if date_to else None, doctor_id, patient_id, status)
