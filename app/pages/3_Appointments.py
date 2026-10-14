from datetime import datetime, timedelta

import streamlit as st

import config
from services import appointment_service, patient_service, staff_service
from utils import clock, ui
from utils.formatting import label

user = ui.require_page("appointments.view")
can_book = ui.can(user, "appointments.edit")
is_doctor = user["role"] == "DOCTOR"

st.title("Appointments" if not is_doctor else "My appointments")
ui.show_flash()

doctors = staff_service.doctor_options(user)
doctor_map = ui.option_map(doctors, "staff_id",
                           lambda d: f"{d['full_name']} · {d['department'] or 'No department'}")
COLUMNS = {"appointment_id": "ID", "date": "Date", "time": "Time", "patient_code": "Patient code",
           "patient_name": "Patient", "doctor_name": "Doctor", "reason": "Reason",
           "status": "Status"}


def with_times(rows):
    return [{**r, "date": r["start_at"][:10],
             "time": f"{r['start_at'][11:16]}–{r['end_at'][11:16]}"} for r in rows]


tabs = st.tabs(["Daily list", "Search"] + (["Book appointment"] if can_book else []))

with tabs[0]:
    c1, c2 = st.columns([1, 2])
    day = c1.date_input("Day", clock.today(), key="day")
    doc = None if is_doctor else c2.selectbox(
        "Doctor", [None, *doctor_map], format_func=lambda d: doctor_map.get(d, "All doctors"))
    rows = appointment_service.search(user, day, day, doctor_id=doc)
    active = [r for r in rows if r["status"] in ("SCHEDULED", "CONFIRMED")]
    st.caption(f"{len(rows)} appointment(s), {len(active)} still to be seen")
    ui.table(ui.frame(with_times(rows), COLUMNS, code_cols=("status",)),
             empty="No appointments on this day.")

    if rows and ui.can(user, "appointments.status"):
        with st.form("status"):
            st.markdown("**Update status**")
            c1, c2 = st.columns([3, 1])
            options = {r["appointment_id"]: f"#{r['appointment_id']} {r['start_at'][11:16]} · "
                                            f"{r['patient_name']} ({label(r['status'])})"
                       for r in rows if r["status"] in appointment_service.TRANSITIONS}
            aid = c1.selectbox("Appointment", list(options), format_func=options.get,
                               index=None, placeholder="Select an open appointment")
            new = c2.selectbox("New status", ["CONFIRMED", "COMPLETED", "CANCELLED", "NO_SHOW"],
                               format_func=label)
            if st.form_submit_button("Update", type="primary"):
                if aid is None:
                    st.error("Select an appointment.")
                else:
                    ui.run_action(appointment_service.update_status, user, aid, new,
                                  success="Appointment updated.")

    if can_book:
        open_rows = [r for r in rows if r["status"] in appointment_service.TRANSITIONS]
        if open_rows:
            with st.expander("Reschedule an appointment"):
                with st.form("reschedule"):
                    options = {r["appointment_id"]: f"#{r['appointment_id']} {r['start_at'][11:16]}"
                                                    f" · {r['patient_name']}" for r in open_rows}
                    aid = st.selectbox("Appointment", list(options), format_func=options.get)
                    c1, c2, c3 = st.columns(3)
                    new_day = c1.date_input("New date", clock.today(), min_value=clock.today())
                    new_time = c2.time_input("New start", datetime.strptime("10:00", "%H:%M").time(),
                                             step=timedelta(minutes=15))
                    mins = c3.number_input("Duration (minutes)", 5, 240,
                                           config.DEFAULT_APPOINTMENT_MINUTES, step=5)
                    if st.form_submit_button("Reschedule"):
                        start = datetime.combine(new_day, new_time)
                        ui.run_action(appointment_service.reschedule, user, aid, start,
                                      start + timedelta(minutes=int(mins)),
                                      success="Appointment rescheduled.")

with tabs[1]:
    start, end = ui.date_range("appt", default_days=7, future_days=7)
    c1, c2 = st.columns(2)
    status = c1.selectbox("Status", [None, *appointment_service.STATUSES],
                          format_func=lambda s: label(s) if s else "All statuses")
    doc = None if is_doctor else c2.selectbox(
        "Doctor", [None, *doctor_map], format_func=lambda d: doctor_map.get(d, "All doctors"),
        key="search_doc")
    rows = appointment_service.search(user, start, end, doctor_id=doc, status=status)
    st.caption(f"{len(rows)} appointment(s)")
    ui.table(ui.frame(with_times(rows), COLUMNS, code_cols=("status",)),
             empty="No appointments match the filters.")

if can_book:
    with tabs[2]:
        patients = ui.option_map(patient_service.options(user), "patient_id",
                                 lambda p: f"{p['patient_code']} · {p['full_name']}")
        with st.form("book", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                pid = ui.select_id("Patient *", patients)
            with c2:
                did = ui.select_id("Doctor *", doctor_map)
            c3, c4, c5 = st.columns(3)
            day = c3.date_input("Date *", clock.today(), min_value=clock.today())
            start_time = c4.time_input("Start time *", datetime.strptime("10:00", "%H:%M").time(),
                                       step=timedelta(minutes=15))
            minutes = c5.number_input("Duration (minutes)", 5, 240,
                                      config.DEFAULT_APPOINTMENT_MINUTES, step=5)
            reason = st.text_input("Reason / visit category")
            ok = st.form_submit_button("Book appointment", type="primary")
        if ok:
            if not pid or not did:
                st.error("Select both a patient and a doctor.")
            else:
                start = datetime.combine(day, start_time)
                appt = ui.run_action(appointment_service.book, user, pid, did, start,
                                     start + timedelta(minutes=int(minutes)), reason, rerun=False)
                if appt:
                    ui.flash("success", f"Booked {appt['patient_name']} with {appt['doctor_name']}"
                                        f" on {appt['start_at'][:16]}.")
                    st.rerun()
        st.caption("A doctor cannot have overlapping scheduled, confirmed or completed "
                   "appointments. Cancelled and no-show appointments free the slot.")
