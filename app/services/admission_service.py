import math
import sqlite3
from datetime import datetime

from database import read_connection, transaction
from repositories import admission_repository, billing_repository, patient_repository
from repositories import staff_repository
from services import audit_service
from utils import clock
from utils import validators as v
from utils.permissions import require

BED_STATUSES = ("AVAILABLE", "UNAVAILABLE", "MAINTENANCE")


# --- wards & beds ----------------------------------------------------------

def list_wards(user):
    require(user, "admissions.view")
    with read_connection() as conn:
        return admission_repository.list_wards(conn)


def add_ward(user, name, ward_type=None, floor=None) -> int:
    require(user, "wards.manage")
    name = v.required_text(name, "Ward name", max_len=80)
    with transaction() as conn:
        if any(w["name"].lower() == name.lower() for w in admission_repository.list_wards(conn)):
            raise v.ValidationError(f"Ward '{name}' already exists.")
        ward_id = admission_repository.insert_ward(conn, name, v.clean_text(ward_type),
                                                   v.clean_text(floor, max_len=20))
        audit_service.log(conn, user, "CREATE", "ward", ward_id)
        return ward_id


def add_bed(user, ward_id, bed_code, daily_rate_minor=0) -> int:
    require(user, "wards.manage")
    bed_code = v.required_text(bed_code, "Bed code", max_len=20).upper()
    v.money_minor(daily_rate_minor, "Daily rate")
    with transaction() as conn:
        if admission_repository.get_ward(conn, ward_id) is None:
            raise v.ValidationError("Select an existing ward.")
        try:
            bed_id = admission_repository.insert_bed(conn, ward_id, bed_code, daily_rate_minor)
        except sqlite3.IntegrityError:
            raise v.ValidationError(f"Bed code '{bed_code}' already exists.") from None
        audit_service.log(conn, user, "CREATE", "bed", bed_id, bed_code)
        return bed_id


def set_bed_status(user, bed_id, status):
    require(user, "wards.manage")
    v.choice(status, BED_STATUSES, "Bed status")
    with transaction() as conn:
        if admission_repository.get_bed(conn, bed_id) is None:
            raise v.ValidationError("Bed not found.")
        if status != "AVAILABLE" and admission_repository.bed_has_active_admission(conn, bed_id):
            raise v.ValidationError("An occupied bed cannot be taken out of service. "
                                    "Discharge or move the patient first.")
        admission_repository.set_bed_status(conn, bed_id, status)
        audit_service.log(conn, user, "STATUS", "bed", bed_id, status)


def set_bed_rate(user, bed_id, daily_rate_minor):
    require(user, "wards.manage")
    v.money_minor(daily_rate_minor, "Daily rate")
    with transaction() as conn:
        admission_repository.set_bed_rate(conn, bed_id, daily_rate_minor)
        audit_service.log(conn, user, "UPDATE", "bed", bed_id, "daily rate")


def bed_board(user, ward_id=None):
    require(user, "admissions.view")
    with read_connection() as conn:
        return admission_repository.bed_board(conn, ward_id)


def available_beds(user):
    require(user, "admissions.view")
    with read_connection() as conn:
        return admission_repository.available_beds(conn)


def occupancy_by_ward(user):
    require(user, "dashboard.view")
    with read_connection() as conn:
        return admission_repository.occupancy_by_ward(conn)


# --- admissions ------------------------------------------------------------

def admit(user, patient_id, bed_id, admitted_at: datetime | None = None, doctor_id=None,
          reason=None) -> dict:
    require(user, "admissions.edit")
    admitted_at = admitted_at or clock.now()
    if admitted_at > clock.now():
        raise v.ValidationError("Admission time cannot be in the future.")
    with transaction() as conn:
        patient = patient_repository.get(conn, patient_id)
        if patient is None or patient["status"] != "ACTIVE":
            raise v.ValidationError("Select an existing, active patient.")
        if admission_repository.active_for_patient(conn, patient_id):
            raise v.ValidationError("This patient is already admitted.")
        bed = admission_repository.get_bed(conn, bed_id)
        if bed is None:
            raise v.ValidationError("Bed not found.")
        if bed["operational_status"] != "AVAILABLE":
            raise v.ValidationError(
                f"Bed {bed['bed_code']} is {bed['operational_status'].lower()} and cannot be assigned.")
        if admission_repository.bed_has_active_admission(conn, bed_id):
            raise v.ValidationError(f"Bed {bed['bed_code']} is already occupied.")
        if doctor_id:
            doctor = staff_repository.get(conn, doctor_id)
            if doctor is None or doctor["role"] != "DOCTOR" or doctor["status"] != "ACTIVE":
                raise v.ValidationError("Attending doctor must be an active doctor.")
        try:
            admission_id = admission_repository.insert_admission(
                conn, patient_id, bed_id, doctor_id, clock.ts(admitted_at),
                v.clean_text(reason, max_len=200), user["user_id"])
        except sqlite3.IntegrityError:
            # The partial unique indexes are the final guard against races.
            raise v.ValidationError("The bed or patient was just assigned elsewhere. "
                                    "Refresh and try again.") from None
        audit_service.log(conn, user, "ADMIT", "admission", admission_id, bed["bed_code"])
        return admission_repository.get_admission(conn, admission_id)


def bed_charge(admission: dict, discharged_at: datetime) -> tuple[int, int]:
    """(days, amount_minor). Any part of a day counts as a full day; minimum 1."""
    admitted = clock.parse_ts(admission["admitted_at"])
    days = max(1, math.ceil((discharged_at - admitted).total_seconds() / 86400))
    return days, days * (admission["daily_rate_minor"] or 0)


def discharge(user, admission_id, discharged_at: datetime | None = None, notes=None,
              create_bed_bill: bool = False) -> int | None:
    """Close the admission (which frees the bed) and optionally raise the bed-charge
    bill, all in one transaction. Returns the bill id if one was created."""
    require(user, "admissions.edit")
    if create_bed_bill:
        require(user, "billing.edit")
    discharged_at = discharged_at or clock.now()
    if discharged_at > clock.now():
        raise v.ValidationError("Discharge time cannot be in the future.")
    with transaction() as conn:
        adm = admission_repository.get_admission(conn, admission_id)
        if adm is None or adm["status"] != "ADMITTED":
            raise v.ValidationError("Select an active admission.")
        if clock.ts(discharged_at) < adm["admitted_at"]:
            raise v.ValidationError("Discharge cannot be before the admission time.")
        if admission_repository.discharge(conn, admission_id, clock.ts(discharged_at),
                                          v.clean_text(notes, max_len=300)) != 1:
            raise v.ValidationError("The admission changed; refresh and try again.")
        audit_service.log(conn, user, "DISCHARGE", "admission", admission_id)
        bill_id = None
        if create_bed_bill:
            days, amount = bed_charge(adm, discharged_at)
            bill_id = billing_repository.insert_bill(
                conn, adm["patient_id"], admission_id, None, clock.ds(discharged_at.date()),
                amount, 0, 0, amount, "Bed charges on discharge", user["user_id"])
            billing_repository.insert_item(conn, bill_id,
                                           f"Bed {adm['bed_code']} ({adm['ward']})", days,
                                           adm["daily_rate_minor"] or 0)
            audit_service.log(conn, user, "CREATE", "bill", bill_id, "bed charges")
        return bill_id


def cancel(user, admission_id, notes):
    """For admissions recorded in error. Frees the bed without a discharge."""
    require(user, "admissions.edit")
    notes = v.required_text(notes, "Cancellation reason", max_len=300)
    with transaction() as conn:
        if admission_repository.cancel(conn, admission_id, notes) != 1:
            raise v.ValidationError("Only an active admission can be cancelled.")
        audit_service.log(conn, user, "CANCEL", "admission", admission_id)


def search(user, status=None, patient_id=None, date_from=None, date_to=None):
    require(user, "admissions.view")
    with read_connection() as conn:
        return admission_repository.search(conn, status, patient_id,
                                           date_from.isoformat() if date_from else None,
                                           date_to.isoformat() if date_to else None)
