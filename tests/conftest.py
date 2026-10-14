import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import database  # noqa: E402
from services import auth_service, patient_service, staff_service  # noqa: E402


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Every test gets its own empty database file; the demo DB is never touched."""
    monkeypatch.setenv("HMS_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("HMS_PBKDF2_ITERATIONS", "1000")
    monkeypatch.delenv("HMS_DEMO_MODE", raising=False)
    monkeypatch.delenv("HMS_AUTO_SEED_DEMO", raising=False)
    database.init_db()
    yield tmp_path / "test.db"


@pytest.fixture
def admin():
    uid = auth_service.create_first_admin("admin", "Test Admin", "Admin@123")
    return auth_service.load_user(uid)


@pytest.fixture
def make_user(admin):
    def _make(role, staff_id=None):
        uid = auth_service.create_user(admin, f"{role.lower()}_user", f"{role} User",
                                       "Passw0rd!", role, staff_id)
        return auth_service.load_user(uid)
    return _make


@pytest.fixture
def patient(admin):
    return patient_service.register(admin, {"full_name": "Test Patient",
                                            "date_of_birth": date(1990, 5, 17),
                                            "phone": "9876543210"})


@pytest.fixture
def doctor(admin):
    dept = staff_service.save_department(admin, "General Medicine")
    return staff_service.create(admin, {"full_name": "Dr. Test", "role": "DOCTOR",
                                        "department_id": dept})


@pytest.fixture
def tomorrow_at():
    def _at(hour, minute=0):
        return datetime.combine(date.today() + timedelta(days=1),
                                datetime.min.time()).replace(hour=hour, minute=minute)
    return _at
