from datetime import date, timedelta

import pytest

from database import read_connection
from services import patient_service
from utils.validators import ValidationError


def test_t01_register_valid_patient(admin):
    p = patient_service.register(admin, {"full_name": "  Meera   Iyer ", "phone": "98765-43210",
                                         "date_of_birth": date(1985, 1, 2)})
    assert p["patient_code"] == f"PAT-{p['patient_id']:06d}"
    assert p["full_name"] == "Meera Iyer"
    assert p["phone"] == "9876543210"
    assert [r["patient_id"] for r in patient_service.search(admin)] == [p["patient_id"]]


def test_t02_blank_name_rejected_and_no_row(admin):
    with pytest.raises(ValidationError, match="name is required"):
        patient_service.register(admin, {"full_name": "   "})
    with read_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 0


@pytest.mark.parametrize("data, message", [
    ({"date_of_birth": date.today() + timedelta(days=1)}, "future"),
    ({"phone": "12345"}, "10 to 15 digits"),
    ({"email": "not-an-email"}, "Email"),
    ({"gender": "UNKNOWN"}, "Gender"),
])
def test_invalid_fields_rejected(admin, data, message):
    with pytest.raises(ValidationError, match=message):
        patient_service.register(admin, {"full_name": "Someone", **data})


def test_t03_search_by_name_code_and_phone(admin, patient):
    other = patient_service.register(admin, {"full_name": "Arjun Das", "phone": "9123456780"})
    assert [p["patient_id"] for p in patient_service.search(admin, "arjun")] == [other["patient_id"]]
    assert [p["patient_id"] for p in patient_service.search(admin, patient["patient_code"])] == \
        [patient["patient_id"]]
    assert [p["patient_id"] for p in patient_service.search(admin, "91234")] == [other["patient_id"]]


def test_t15_search_with_no_match_and_wildcards(admin, patient):
    assert patient_service.search(admin, "zzz-nobody") == []
    assert patient_service.search(admin, "%") == []  # LIKE wildcards are escaped


def test_duplicate_detection(admin, patient):
    data = {"full_name": "test patient", "phone": "9876543210"}
    with pytest.raises(ValidationError, match="already exists"):
        patient_service.register(admin, data)
    assert patient_service.register(admin, data, allow_duplicate=True)


def test_update_and_archive(admin, patient):
    updated = patient_service.update(admin, patient["patient_id"],
                                     {"full_name": "Renamed Patient", "phone": "9000000000"})
    assert updated["full_name"] == "Renamed Patient"
    patient_service.set_status(admin, patient["patient_id"], False)
    assert patient_service.get(admin, patient["patient_id"])["status"] == "INACTIVE"
    assert patient_service.options(admin) == []  # archived patients are not selectable


def test_sql_injection_text_is_stored_literally(admin):
    name = "Robert'); DROP TABLE patients;--"
    p = patient_service.register(admin, {"full_name": name})
    assert patient_service.get(admin, p["patient_id"])["full_name"] == name
