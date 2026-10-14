import streamlit as st

from services import patient_service
from utils import clock, ui
from utils.formatting import label

user = ui.require_page("patients.view")
can_edit = ui.can(user, "patients.edit")

st.title("Patients")
ui.show_flash()

PATIENT_COLUMNS = {"patient_code": "Code", "full_name": "Name", "gender": "Gender",
                   "date_of_birth": "Date of birth", "phone": "Phone", "status": "Status",
                   "created_at": "Registered"}


def patient_form(key: str, existing: dict | None = None):
    e = existing or {}
    with st.form(key, clear_on_submit=existing is None):
        c1, c2, c3 = st.columns(3)
        full_name = c1.text_input("Full name *", e.get("full_name", ""))
        dob = c2.date_input("Date of birth",
                            clock.parse_date(e["date_of_birth"]) if e.get("date_of_birth") else None,
                            min_value=clock.parse_date("1900-01-01"), max_value=clock.today())
        genders = [None, *patient_service.GENDERS]
        gender = c3.selectbox("Gender", genders, index=genders.index(e.get("gender")),
                              format_func=lambda g: label(g) if g else "Not specified")
        c4, c5, c6 = st.columns(3)
        phone = c4.text_input("Phone", e.get("phone") or "",
                              help="10-15 digits, optional leading +")
        email = c5.text_input("Email", e.get("email") or "")
        bgs = [None, *patient_service.BLOOD_GROUPS]
        blood = c6.selectbox("Blood group", bgs, index=bgs.index(e.get("blood_group")),
                             format_func=lambda b: b or "Unknown")
        address = st.text_input("Address", e.get("address") or "")
        emergency = st.text_input("Emergency contact (name and phone)",
                                  e.get("emergency_contact") or "")
        allow_dup = False
        if existing is None:
            allow_dup = st.checkbox("Register even if a similar patient already exists")
        submitted = st.form_submit_button("Save patient" if existing else "Register patient",
                                          type="primary")
    data = {"full_name": full_name, "date_of_birth": dob, "gender": gender, "phone": phone,
            "email": email, "blood_group": blood, "address": address,
            "emergency_contact": emergency}
    return submitted, data, allow_dup


tabs = st.tabs(["Search", "Register", "Patient record"] if can_edit else ["Search", "Patient record"])
search_tab, record_tab = tabs[0], tabs[-1]

with search_tab:
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    term = c1.text_input("Search by code, name or phone", key="p_term")
    status = c2.selectbox("Status", [None, "ACTIVE", "INACTIVE"],
                          format_func=lambda s: label(s) if s else "All")
    reg_from = c3.date_input("Registered from", None, key="p_from")
    reg_to = c4.date_input("Registered to", None, key="p_to")
    rows = patient_service.search(user, term, status, reg_from, reg_to)
    st.caption(f"{len(rows)} patient(s)")
    ui.table(ui.frame(rows, PATIENT_COLUMNS, code_cols=("gender", "status")),
             empty="No patients match your search.")

if can_edit:
    with tabs[1]:
        submitted, data, allow_dup = patient_form("register")
        if submitted:
            created = ui.run_action(patient_service.register, user, data, allow_dup, rerun=False)
            if created:
                ui.flash("success", f"Registered {created['full_name']} as {created['patient_code']}.")
                st.rerun()

with record_tab:
    options = ui.option_map(patient_service.options(user, active_only=False), "patient_id",
                            lambda p: f"{p['patient_code']} · {p['full_name']}")
    pid = ui.select_id("Select patient", options, key="p_record")
    if pid:
        p = patient_service.get(user, pid)
        st.subheader(f"{p['full_name']} ({p['patient_code']})")
        info = st.columns(4)
        info[0].metric("Status", label(p["status"]))
        if p["date_of_birth"]:
            dob = clock.parse_date(p["date_of_birth"])
            today = clock.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            info[1].metric("Age", f"{age} years")
        info[2].metric("Gender", label(p["gender"]) or "—")
        info[3].metric("Blood group", p["blood_group"] or "—")
        st.caption(f"Phone: {p['phone'] or '—'} · Email: {p['email'] or '—'} · "
                   f"Registered: {p['created_at'][:10]}")

        hist = patient_service.history(user, pid)
        h1, h2, h3 = st.tabs(["Appointments", "Admissions", "Bills"])
        with h1:
            ui.table(ui.frame(hist["appointments"], {"start_at": "Start", "doctor_name": "Doctor",
                                                     "department": "Department",
                                                     "reason": "Reason", "status": "Status"},
                              code_cols=("status",)), empty="No appointments.")
        with h2:
            ui.table(ui.frame(hist["admissions"], {"admitted_at": "Admitted",
                                                   "discharged_at": "Discharged", "ward": "Ward",
                                                   "bed_code": "Bed", "status": "Status"},
                              code_cols=("status",)), empty="No admissions.")
        with h3:
            if ui.can(user, "billing.view"):
                ui.table(ui.frame(hist["bills"], {"bill_number": "Bill", "bill_date": "Date",
                                                  "total_minor": "Total", "paid_minor": "Paid",
                                                  "balance_minor": "Balance", "status": "Status"},
                                  money_cols=("total_minor", "paid_minor", "balance_minor"),
                                  code_cols=("status",)),
                         money=("Total", "Paid", "Balance"), empty="No bills.")
            else:
                st.info("Billing details are visible to billing staff and administrators.")

        if can_edit:
            with st.expander("Edit details"):
                submitted, data, _ = patient_form(f"edit_{pid}", p)
                if submitted:
                    ui.run_action(patient_service.update, user, pid, data,
                                  success="Patient details updated.")
            if p["status"] == "ACTIVE":
                if st.button("Archive patient", help="Marks the record inactive; history is kept."):
                    ui.run_action(patient_service.set_status, user, pid, False,
                                  success="Patient archived.")
            elif st.button("Reactivate patient"):
                ui.run_action(patient_service.set_status, user, pid, True,
                              success="Patient reactivated.")
