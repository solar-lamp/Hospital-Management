from database import read_connection, transaction
from repositories import (admission_repository, appointment_repository, billing_repository,
                          patient_repository)
from services import audit_service
from utils import validators as v
from utils.permissions import has_permission, require

GENDERS = ("MALE", "FEMALE", "OTHER")
BLOOD_GROUPS = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")


def _clean(data: dict) -> dict:
    dob = v.date_of_birth(data.get("date_of_birth"))
    gender = data.get("gender") or None
    if gender:
        v.choice(gender, GENDERS, "Gender")
    blood = data.get("blood_group") or None
    if blood:
        v.choice(blood, BLOOD_GROUPS, "Blood group")
    return {
        "full_name": v.required_text(data.get("full_name"), "Patient name", max_len=100),
        "date_of_birth": dob.isoformat() if dob else None,
        "gender": gender,
        "blood_group": blood,
        "phone": v.phone(data.get("phone")),
        "email": v.email(data.get("email")),
        "address": v.clean_text(data.get("address"), max_len=300),
        "emergency_contact": v.clean_text(data.get("emergency_contact"), max_len=150),
    }


def register(user, data: dict, allow_duplicate: bool = False) -> dict:
    require(user, "patients.edit")
    clean = _clean(data)
    with transaction() as conn:
        if not allow_duplicate:
            dups = patient_repository.find_duplicates(
                conn, clean["full_name"], clean["date_of_birth"], clean["phone"])
            if dups:
                codes = ", ".join(d["patient_code"] for d in dups)
                raise v.ValidationError(
                    f"A patient with the same name and date of birth or phone already exists ({codes}).")
        patient_id = patient_repository.insert(conn, clean)
        audit_service.log(conn, user, "CREATE", "patient", patient_id)
        return patient_repository.get(conn, patient_id)


def update(user, patient_id: int, data: dict) -> dict:
    require(user, "patients.edit")
    clean = _clean(data)
    with transaction() as conn:
        if patient_repository.get(conn, patient_id) is None:
            raise v.ValidationError("Patient not found.")
        patient_repository.update(conn, patient_id, clean)
        audit_service.log(conn, user, "UPDATE", "patient", patient_id)
        return patient_repository.get(conn, patient_id)


def set_status(user, patient_id: int, active: bool):
    """Archive (INACTIVE) or re-activate. Patients are never hard-deleted."""
    require(user, "patients.edit")
    status = "ACTIVE" if active else "INACTIVE"
    with transaction() as conn:
        if patient_repository.get(conn, patient_id) is None:
            raise v.ValidationError("Patient not found.")
        if not active and admission_repository.active_for_patient(conn, patient_id):
            raise v.ValidationError("Discharge the patient before archiving the record.")
        patient_repository.set_status(conn, patient_id, status)
        audit_service.log(conn, user, "ARCHIVE" if not active else "REACTIVATE",
                          "patient", patient_id)


def get(user, patient_id):
    require(user, "patients.view")
    with read_connection() as conn:
        return patient_repository.get(conn, patient_id)


def search(user, term=None, status=None, registered_from=None, registered_to=None):
    require(user, "patients.view")
    with read_connection() as conn:
        return patient_repository.search(conn, (term or "").strip() or None, status,
                                         registered_from, registered_to)


def options(user, active_only=True):
    """Lightweight list for select boxes. Requires any patient-facing permission."""
    if not any(has_permission(user, p) for p in ("patients.view", "appointments.edit",
                                       "admissions.edit", "billing.edit")):
        require(user, "patients.view")
    with read_connection() as conn:
        return patient_repository.options(conn, active_only)


def history(user, patient_id):
    require(user, "patients.view")
    with read_connection() as conn:
        out = {
            "appointments": appointment_repository.search(conn, patient_id=patient_id),
            "admissions": admission_repository.search(conn, patient_id=patient_id),
            "bills": [],
        }
        if has_permission(user, "billing.view"):
            out["bills"] = billing_repository.search(conn, patient_id=patient_id)
        return out
