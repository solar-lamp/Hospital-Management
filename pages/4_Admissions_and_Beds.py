from datetime import datetime

import pandas as pd
import streamlit as st

from services import admission_service, patient_service, staff_service
from utils import clock, ui
from utils.formatting import label, money, to_minor

user = ui.require_page("admissions.view")
can_edit = ui.can(user, "admissions.edit")
can_manage = ui.can(user, "wards.manage")

st.title("Admissions & Beds")
ui.show_flash()

board = admission_service.bed_board(user)
counts = pd.Series([b["occupancy"] for b in board]).value_counts() if board else pd.Series()
c = st.columns(4)
c[0].metric("Total beds", len(board))
c[1].metric("Occupied", int(counts.get("OCCUPIED", 0)))
c[2].metric("Available", int(counts.get("AVAILABLE", 0)))
c[3].metric("Out of service", int(counts.get("MAINTENANCE", 0) + counts.get("UNAVAILABLE", 0)))

names = ["Bed board", "Current admissions"]
if can_edit:
    names += ["Admit patient", "Discharge"]
names.append("History")
if can_manage:
    names.append("Wards & beds")
tabs = dict(zip(names, st.tabs(names)))

ICON = {"OCCUPIED": "🔴", "AVAILABLE": "🟢", "MAINTENANCE": "🛠️", "UNAVAILABLE": "⚪"}

with tabs["Bed board"]:
    wards = admission_service.list_wards(user)
    if not wards:
        st.info("No wards configured yet.")
    for ward in wards:
        beds = [b for b in board if b["ward_id"] == ward["ward_id"]]
        occupied = sum(1 for b in beds if b["occupancy"] == "OCCUPIED")
        st.markdown(f"**{ward['name']}** · {ward['ward_type'] or ''} · floor {ward['floor'] or '—'}"
                    f" · {occupied}/{len(beds)} occupied")
        cols = st.columns(8)
        for i, b in enumerate(beds):
            with cols[i % 8].container(border=True):
                st.markdown(f"{ICON[b['occupancy']]} **{b['bed_code']}**")
                st.caption(b["patient_code"] if b["patient_code"] else label(b["occupancy"]))
    st.caption("🟢 available · 🔴 occupied · 🛠️ maintenance · ⚪ unavailable. A bed is "
               "available only when it is operational and has no active admission.")

active = admission_service.search(user, status="ADMITTED")
ADM_COLS = {"admission_id": "ID", "patient_code": "Patient code", "patient_name": "Patient",
            "ward": "Ward", "bed_code": "Bed", "doctor_name": "Doctor", "admitted_at": "Admitted",
            "discharged_at": "Discharged", "reason": "Reason", "status": "Status"}

with tabs["Current admissions"]:
    ui.table(ui.frame(active, ADM_COLS, code_cols=("status",)),
             empty="No patients are currently admitted.")

if can_edit:
    with tabs["Admit patient"]:
        free = admission_service.available_beds(user)
        patients = ui.option_map(patient_service.options(user), "patient_id",
                                 lambda p: f"{p['patient_code']} · {p['full_name']}")
        admitted_ids = {a["patient_id"] for a in active}
        patients = {k: v for k, v in patients.items() if k not in admitted_ids}
        beds = ui.option_map(free, "bed_id", lambda b: f"{b['bed_code']} · {b['ward']}"
                                                       f" · {money(b['daily_rate_minor'])}/day")
        doctors = ui.option_map(staff_service.doctor_options(user), "staff_id",
                                lambda d: d["full_name"])
        with st.form("admit", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                pid = ui.select_id("Patient *", patients)
            with c2:
                bid = ui.select_id("Available bed *", beds)
            c3, c4, c5 = st.columns(3)
            with c3:
                did = ui.select_id("Attending doctor", doctors)
            day = c4.date_input("Admission date", clock.today(), max_value=clock.today())
            at = c5.time_input("Admission time", clock.now().time().replace(second=0))
            reason = st.text_input("Reason for admission")
            ok = st.form_submit_button("Admit patient", type="primary")
        if ok:
            if not pid or not bid:
                st.error("Select a patient and a bed.")
            else:
                ui.run_action(admission_service.admit, user, pid, bid,
                              datetime.combine(day, at), did, reason,
                              success="Patient admitted.")

    with tabs["Discharge"]:
        if not active:
            st.info("No active admissions.")
        else:
            options = {a["admission_id"]: f"{a['patient_name']} ({a['patient_code']}) · "
                                          f"{a['bed_code']} since {a['admitted_at'][:16]}"
                       for a in active}
            with st.form("discharge"):
                aid = st.selectbox("Admission *", list(options), format_func=options.get)
                c1, c2 = st.columns(2)
                day = c1.date_input("Discharge date", clock.today(), max_value=clock.today())
                at = c2.time_input("Discharge time", clock.now().time().replace(second=0))
                notes = st.text_area("Discharge notes")
                bill = st.checkbox("Create bed-charge bill", value=ui.can(user, "billing.edit"),
                                   disabled=not ui.can(user, "billing.edit"),
                                   help="Days x bed daily rate; part days count as full days.")
                confirm = st.checkbox("I confirm this is the correct patient and admission")
                ok = st.form_submit_button("Discharge", type="primary")
            if ok:
                if not confirm:
                    st.error("Please confirm the selected admission.")
                else:
                    ui.run_action(admission_service.discharge, user, aid,
                                  datetime.combine(day, at), notes, bill,
                                  success="Patient discharged and bed released.")
            with st.expander("Cancel an admission recorded in error"):
                with st.form("cancel_adm"):
                    aid2 = st.selectbox("Admission", list(options), format_func=options.get)
                    why = st.text_input("Reason *")
                    if st.form_submit_button("Cancel admission"):
                        ui.run_action(admission_service.cancel, user, aid2, why,
                                      success="Admission cancelled.")

with tabs["History"]:
    start, end = ui.date_range("adm", default_days=30)
    status = st.selectbox("Status", [None, "ADMITTED", "DISCHARGED", "CANCELLED"],
                          format_func=lambda s: label(s) if s else "All")
    rows = admission_service.search(user, status, None, start, end)
    ui.table(ui.frame(rows, ADM_COLS, code_cols=("status",)), empty="No admissions found.")

if can_manage:
    with tabs["Wards & beds"]:
        wards = admission_service.list_wards(user)
        ward_map = {w["ward_id"]: w["name"] for w in wards}
        c1, c2 = st.columns(2)
        with c1.form("ward", clear_on_submit=True):
            st.markdown("**Add ward**")
            name = st.text_input("Ward name *")
            wtype = st.text_input("Type", placeholder="General, ICU, Private...")
            floor = st.text_input("Floor")
            if st.form_submit_button("Add ward"):
                ui.run_action(admission_service.add_ward, user, name, wtype, floor,
                              success="Ward added.")
        with c2.form("bed", clear_on_submit=True):
            st.markdown("**Add bed**")
            wid = st.selectbox("Ward", list(ward_map), format_func=ward_map.get)
            code = st.text_input("Bed code *", placeholder="GWA-09")
            rate = st.number_input("Daily rate (₹)", min_value=0.0, step=100.0)
            if st.form_submit_button("Add bed"):
                ui.run_action(admission_service.add_bed, user, wid, code, to_minor(rate),
                              success="Bed added.")
        st.markdown("**Bed status and rates**")
        with st.form("bedstatus"):
            bed_map = {b["bed_id"]: f"{b['bed_code']} · {b['ward']} ({label(b['occupancy'])})"
                       for b in board}
            c1, c2, c3 = st.columns(3)
            bid = c1.selectbox("Bed", list(bed_map), format_func=bed_map.get)
            status = c2.selectbox("Operational status", admission_service.BED_STATUSES,
                                  format_func=label)
            rate = c3.number_input("Daily rate (₹, leave 0 to keep)", min_value=0.0, step=100.0)
            if st.form_submit_button("Update bed"):
                def update_bed():
                    admission_service.set_bed_status(user, bid, status)
                    if rate > 0:
                        admission_service.set_bed_rate(user, bid, to_minor(rate))
                ui.run_action(update_bed, success="Bed updated.")
