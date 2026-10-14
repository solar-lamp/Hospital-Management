"""UI smoke tests: every page renders for every role without exceptions, and
pages outside a role's permissions are refused even when opened directly."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import seed
from utils.permissions import has_permission

ROOT = Path(__file__).resolve().parents[1]

PAGES = {
    "pages/0_Dashboard.py": "dashboard.view",
    "pages/1_Patients.py": "patients.view",
    "pages/2_Doctors_and_Staff.py": "staff.view",
    "pages/3_Appointments.py": "appointments.view",
    "pages/4_Admissions_and_Beds.py": "admissions.view",
    "pages/5_Medicine_Inventory.py": "pharmacy.view",
    "pages/6_Suppliers.py": "suppliers.view",
    "pages/7_Billing_and_Payments.py": "billing.view",
    "pages/8_Reports.py": "reports.view",
    "pages/9_User_Management.py": "users.manage",
    "pages/10_Settings.py": "dashboard.view",
}


@pytest.fixture
def seeded():
    seed.seed_demo()


def login(username, password):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.run()
    at.text_input[0].input(username)
    at.text_input[1].input(password)
    at.button[0].click()
    at.run()
    return at


def test_first_run_shows_setup():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    assert "Welcome to MediTrack" in [t.value for t in at.title]


def test_bad_login_shows_error(seeded):
    at = login("admin", "nope")
    assert any("Invalid username or password" in e.value for e in at.error)


@pytest.mark.parametrize("username, password, role", [
    (u, p, r) for u, p, r, _, _ in seed.DEMO_USERS])
def test_every_page_for_every_role(seeded, username, password, role):
    at = login(username, password)
    assert not at.exception, at.exception
    assert at.title[0].value in ("Dashboard",)
    user = {"role": role, "active": 1}
    for page, permission in PAGES.items():
        at.switch_page(page).run()
        assert not at.exception, f"{role} {page}: {at.exception}"
        if not has_permission(user, permission):
            # Direct navigation outside the role must not show page content.
            titles = [t.value for t in at.title]
            assert len(titles) <= 1, f"{role} could open {page}"


def test_patient_registration_through_ui(seeded):
    at = login("reception", "Reception@123")
    at.switch_page("pages/1_Patients.py").run()
    form_inputs = [t for t in at.text_input if t.label == "Full name *"]
    form_inputs[0].input("UI Created Patient")
    [b for b in at.button if b.label == "Register patient"][0].click()
    at.run()
    assert not at.exception
    assert any("UI Created Patient" in s.value for s in at.success)


def test_logout(seeded):
    at = login("admin", "Admin@123")
    [b for b in at.sidebar.button if b.label == "Log out"][0].click()
    at.run()
    assert [b for b in at.button if b.label == "Log in"]
