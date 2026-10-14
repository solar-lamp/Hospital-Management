from datetime import datetime, timedelta

import pytest

from services import appointment_service, staff_service
from utils.permissions import PermissionDenied
from utils.validators import ValidationError


def test_book_valid(admin, patient, doctor, tomorrow_at):
    a = appointment_service.book(admin, patient["patient_id"], doctor["staff_id"],
                                 tomorrow_at(10), tomorrow_at(10, 30), "Check-up")
    assert a["status"] == "SCHEDULED"


def test_t04_end_before_start_rejected(admin, patient, doctor, tomorrow_at):
    with pytest.raises(ValidationError, match="after the start"):
        appointment_service.book(admin, patient["patient_id"], doctor["staff_id"],
                                 tomorrow_at(11), tomorrow_at(10))


def test_t05_overlap_rejected_but_adjacent_ok(admin, patient, doctor, tomorrow_at):
    pid, did = patient["patient_id"], doctor["staff_id"]
    appointment_service.book(admin, pid, did, tomorrow_at(10), tomorrow_at(10, 30))
    with pytest.raises(ValidationError, match="already has an appointment"):
        appointment_service.book(admin, pid, did, tomorrow_at(10, 15), tomorrow_at(10, 45))
    with pytest.raises(ValidationError, match="already has an appointment"):
        appointment_service.book(admin, pid, did, tomorrow_at(9, 45), tomorrow_at(11))
    # Touching intervals do not overlap.
    appointment_service.book(admin, pid, did, tomorrow_at(10, 30), tomorrow_at(11))


def test_cancelled_appointment_frees_slot(admin, patient, doctor, tomorrow_at):
    pid, did = patient["patient_id"], doctor["staff_id"]
    a = appointment_service.book(admin, pid, did, tomorrow_at(10), tomorrow_at(10, 30))
    appointment_service.update_status(admin, a["appointment_id"], "CANCELLED")
    appointment_service.book(admin, pid, did, tomorrow_at(10), tomorrow_at(10, 30))


def test_past_booking_and_non_doctor_rejected(admin, patient, doctor, tomorrow_at):
    past = datetime.now() - timedelta(hours=2)
    with pytest.raises(ValidationError, match="past"):
        appointment_service.book(admin, patient["patient_id"], doctor["staff_id"], past,
                                 past + timedelta(minutes=15))
    nurse = staff_service.create(admin, {"full_name": "Nurse A", "role": "NURSE"})
    with pytest.raises(ValidationError, match="doctor"):
        appointment_service.book(admin, patient["patient_id"], nurse["staff_id"],
                                 tomorrow_at(10), tomorrow_at(10, 15))


def test_status_transitions(admin, patient, doctor, tomorrow_at):
    a = appointment_service.book(admin, patient["patient_id"], doctor["staff_id"],
                                 tomorrow_at(10), tomorrow_at(10, 30))
    with pytest.raises(ValidationError, match="future"):
        appointment_service.update_status(admin, a["appointment_id"], "COMPLETED")
    appointment_service.update_status(admin, a["appointment_id"], "CANCELLED")
    with pytest.raises(ValidationError, match="Cannot change"):
        appointment_service.update_status(admin, a["appointment_id"], "CONFIRMED")


def test_doctor_sees_and_updates_only_own(admin, make_user, patient, doctor, tomorrow_at):
    other = staff_service.create(admin, {"full_name": "Dr. Other", "role": "DOCTOR"})
    mine = appointment_service.book(admin, patient["patient_id"], doctor["staff_id"],
                                    tomorrow_at(10), tomorrow_at(10, 30))
    theirs = appointment_service.book(admin, patient["patient_id"], other["staff_id"],
                                      tomorrow_at(10), tomorrow_at(10, 30))
    doc_user = make_user("DOCTOR", doctor["staff_id"])
    visible = appointment_service.search(doc_user)
    assert [a["appointment_id"] for a in visible] == [mine["appointment_id"]]
    with pytest.raises(PermissionDenied):
        appointment_service.update_status(doc_user, theirs["appointment_id"], "CONFIRMED")
    appointment_service.update_status(doc_user, mine["appointment_id"], "CONFIRMED")
    with pytest.raises(PermissionDenied):
        appointment_service.book(doc_user, patient["patient_id"], doctor["staff_id"],
                                 tomorrow_at(12), tomorrow_at(12, 15))
