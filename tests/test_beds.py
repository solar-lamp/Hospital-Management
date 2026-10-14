from datetime import datetime, timedelta

import pytest

from database import read_connection
from services import admission_service, billing_service, patient_service
from utils.validators import ValidationError


@pytest.fixture
def bed(admin):
    ward = admission_service.add_ward(admin, "Ward A", "General", "1")
    return admission_service.add_bed(admin, ward, "wa-01", 150000)


def test_t06_admit_to_available_bed(admin, patient, bed):
    adm = admission_service.admit(admin, patient["patient_id"], bed)
    assert adm["status"] == "ADMITTED" and adm["bed_code"] == "WA-01"
    assert admission_service.available_beds(admin) == []


def test_t07_second_patient_to_occupied_bed_rejected(admin, patient, bed):
    admission_service.admit(admin, patient["patient_id"], bed)
    other = patient_service.register(admin, {"full_name": "Second Patient"})
    with pytest.raises(ValidationError, match="already occupied"):
        admission_service.admit(admin, other["patient_id"], bed)


def test_database_index_blocks_double_admission(admin, patient, bed):
    """Even bypassing the service, SQLite's partial unique index refuses it."""
    import sqlite3
    admission_service.admit(admin, patient["patient_id"], bed)
    other = patient_service.register(admin, {"full_name": "Second Patient"})
    from database import transaction
    with pytest.raises(sqlite3.IntegrityError):
        with transaction() as conn:
            conn.execute("INSERT INTO admissions (patient_id, bed_id, admitted_at)"
                         " VALUES (?, ?, '2026-01-01 10:00:00')", (other["patient_id"], bed))


def test_patient_cannot_hold_two_beds(admin, patient, bed):
    ward = admission_service.list_wards(admin)[0]["ward_id"]
    bed2 = admission_service.add_bed(admin, ward, "WA-02")
    admission_service.admit(admin, patient["patient_id"], bed)
    with pytest.raises(ValidationError, match="already admitted"):
        admission_service.admit(admin, patient["patient_id"], bed2)


def test_maintenance_bed_cannot_be_assigned(admin, patient, bed):
    admission_service.set_bed_status(admin, bed, "MAINTENANCE")
    with pytest.raises(ValidationError, match="maintenance"):
        admission_service.admit(admin, patient["patient_id"], bed)


def test_occupied_bed_cannot_go_to_maintenance(admin, patient, bed):
    admission_service.admit(admin, patient["patient_id"], bed)
    with pytest.raises(ValidationError, match="occupied bed"):
        admission_service.set_bed_status(admin, bed, "MAINTENANCE")


def test_t08_discharge_releases_bed_and_bills(admin, patient, bed):
    admitted = datetime.now().replace(microsecond=0) - timedelta(days=2, hours=3)
    adm = admission_service.admit(admin, patient["patient_id"], bed, admitted)
    bill_id = admission_service.discharge(admin, adm["admission_id"], notes="Recovered",
                                          create_bed_bill=True)
    assert [b["bed_id"] for b in admission_service.available_beds(admin)] == [bed]
    bill = billing_service.get_bill(admin, bill_id)
    assert bill["items"][0]["quantity"] == 3            # 2 days 3 h -> 3 days
    assert bill["total_minor"] == 3 * 150000
    # The bed can be reused.
    other = patient_service.register(admin, {"full_name": "Next Patient"})
    admission_service.admit(admin, other["patient_id"], bed)


def test_discharge_before_admission_rejected(admin, patient, bed):
    adm = admission_service.admit(admin, patient["patient_id"], bed)
    with pytest.raises(ValidationError, match="before the admission"):
        admission_service.discharge(admin, adm["admission_id"],
                                    datetime.now() - timedelta(days=1))
    with read_connection() as conn:
        assert conn.execute("SELECT status FROM admissions").fetchone()[0] == "ADMITTED"


def test_discharge_with_bill_is_atomic(admin, make_user, patient, bed):
    """A receptionist cannot create bills; the discharge must not happen either."""
    from utils.permissions import PermissionDenied
    reception = make_user("RECEPTIONIST")
    adm = admission_service.admit(reception, patient["patient_id"], bed)
    with pytest.raises(PermissionDenied):
        admission_service.discharge(reception, adm["admission_id"], create_bed_bill=True)
    assert admission_service.search(admin, status="ADMITTED")


def test_cannot_archive_admitted_patient(admin, patient, bed):
    admission_service.admit(admin, patient["patient_id"], bed)
    with pytest.raises(ValidationError, match="Discharge"):
        patient_service.set_status(admin, patient["patient_id"], False)
