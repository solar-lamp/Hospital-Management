"""MediTrack HMS entry point: page config, database bootstrap, login gate and
role-aware navigation. Run with ``streamlit run app.py``."""

import logging

import streamlit as st

import config
import database
from services import auth_service
from utils import ui
from utils.permissions import ROLE_LABELS, has_permission

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

st.set_page_config(page_title=config.APP_NAME, page_icon="🏥", layout="wide",
                   initial_sidebar_state="expanded")


@st.cache_resource(show_spinner="Preparing the database...")
def bootstrap() -> int:
    """Create/upgrade the schema once per server process (and seed the demo
    database on first start when configured)."""
    version = database.init_db()
    if config.auto_seed_demo() and database.is_empty():
        import seed
        seed.seed_demo()
    return version


bootstrap()


def first_run_setup():
    st.title("Welcome to MediTrack")
    st.write("No user accounts exist yet. Create the first administrator account, "
             "or load fictional demo data to explore the system.")
    c1, c2 = st.columns(2)
    with c1.form("first_admin"):
        st.subheader("Create administrator")
        username = st.text_input("Username")
        full_name = st.text_input("Full name")
        p1 = st.text_input("Password", type="password",
                           help="At least 8 characters mixing letters and digits/symbols.")
        p2 = st.text_input("Confirm password", type="password")
        if st.form_submit_button("Create administrator", type="primary"):
            if p1 != p2:
                st.error("Passwords do not match.")
            else:
                ui.run_action(auth_service.create_first_admin, username, full_name, p1,
                              success="Administrator created. Please log in.")
    with c2:
        st.subheader("Or load demo data")
        st.caption("Creates fictional patients, staff, beds, medicines and bills, plus demo "
                   "accounts for every role (see README).")
        if st.button("Load demo data"):
            import seed
            with st.spinner("Creating demo data..."):
                ui.run_action(seed.seed_demo, success="Demo data loaded. Log in as admin / Admin@123.")


def login_page():
    left, mid, right = st.columns([1, 1.4, 1])
    with mid:
        st.markdown("<h1 style='text-align:center;margin-bottom:0'>🏥 MediTrack</h1>",
                    unsafe_allow_html=True)
        st.markdown("<p style='text-align:center;opacity:.75'>Hospital Management and "
                    "Resource Tracking</p>", unsafe_allow_html=True)
        ui.show_flash()
        with st.form("login"):
            username = st.text_input("Username", autocomplete="username")
            password = st.text_input("Password", type="password",
                                     autocomplete="current-password")
            submitted = st.form_submit_button("Log in", type="primary", width="stretch")
        if submitted:
            try:
                with st.spinner("Signing in..."):
                    user = auth_service.authenticate(username, password)
            except auth_service.AuthError as exc:
                st.error(str(exc))
            else:
                ui.login(user)
                st.rerun()
        if config.demo_mode():
            with st.expander("Demo accounts (fictional data)", expanded=True):
                st.markdown(
                    "| Role | Username | Password |\n|---|---|---|\n"
                    "| Administrator | `admin` | `Admin@123` |\n"
                    "| Receptionist | `reception` | `Reception@123` |\n"
                    "| Pharmacist | `pharmacist` | `Pharma@123` |\n"
                    "| Billing staff | `billing` | `Billing@123` |\n"
                    "| Doctor | `doctor` | `Doctor@123` |\n"
                    "| Nurse | `nurse` | `Nurse@123` |")
                st.caption("This demo runs entirely in your browser. Data is stored only on "
                           "this device and can be reset from Settings.")
        st.caption("Educational prototype. Use synthetic data only - not for clinical use.")


# Always route through st.navigation (even before login) so Streamlit never
# auto-lists the files in pages/ to an anonymous visitor.
if not auth_service.has_users():
    st.navigation([st.Page(first_run_setup, title="Setup")], position="hidden").run()
    st.stop()

user = ui.current_user()
if user is None:
    st.navigation([st.Page(login_page, title="Log in")], position="hidden").run()
    st.stop()

# --- role-aware navigation -------------------------------------------------
PAGES = [
    # (section, file, title, icon, permission)
    ("Overview", "pages/0_Dashboard.py", "Dashboard", ":material/dashboard:", "dashboard.view"),
    ("Clinical", "pages/1_Patients.py", "Patients", ":material/personal_injury:", "patients.view"),
    ("Clinical", "pages/3_Appointments.py", "Appointments", ":material/event:",
     "appointments.view"),
    ("Clinical", "pages/4_Admissions_and_Beds.py", "Admissions & Beds", ":material/bed:",
     "admissions.view"),
    ("Resources", "pages/2_Doctors_and_Staff.py", "Doctors & Staff", ":material/badge:",
     "staff.view"),
    ("Resources", "pages/5_Medicine_Inventory.py", "Pharmacy & Medicines",
     ":material/medication:", "pharmacy.view"),
    ("Resources", "pages/6_Suppliers.py", "Suppliers & Purchases", ":material/local_shipping:",
     "suppliers.view"),
    ("Finance", "pages/7_Billing_and_Payments.py", "Billing & Payments", ":material/receipt_long:",
     "billing.view"),
    ("Finance", "pages/8_Reports.py", "Reports", ":material/summarize:", "reports.view"),
    ("Admin", "pages/9_User_Management.py", "User Management", ":material/manage_accounts:",
     "users.manage"),
    ("Admin", "pages/10_Settings.py", "Settings & About", ":material/settings:",
     "dashboard.view"),
]

sections: dict[str, list] = {}
for section, path, title, icon, permission in PAGES:
    if has_permission(user, permission):
        sections.setdefault(section, []).append(
            st.Page(path, title=title, icon=icon, default=(title == "Dashboard")))

nav = st.navigation(sections)

with st.sidebar:
    st.markdown(f"**{user['full_name']}**  \n{ROLE_LABELS.get(user['role'], user['role'])}"
                f" · `{user['username']}`")
    if st.button("Log out", icon=":material/logout:", width="stretch"):
        ui.logout()
        st.rerun()
    st.caption("MediTrack HMS · demo build" if config.demo_mode() else "MediTrack HMS")

nav.run()
