import streamlit as st

from services import staff_service
from utils import clock, ui
from utils.formatting import label

user = ui.require_page("staff.view")
can_edit = ui.can(user, "staff.edit")

st.title("Doctors & Staff")
ui.show_flash()

departments = staff_service.list_departments(user)
dept_options = {d["department_id"]: d["name"] for d in departments}
COLUMNS = {"staff_code": "Code", "full_name": "Name", "role": "Role", "department": "Department",
           "specialization": "Specialization", "phone": "Phone", "joining_date": "Joined",
           "status": "Status"}


def staff_form(key, existing=None):
    e = existing or {}
    with st.form(key, clear_on_submit=existing is None):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Full name *", e.get("full_name", ""))
        roles = list(staff_service.STAFF_ROLES)
        role = c2.selectbox("Role *", roles, index=roles.index(e.get("role", "DOCTOR")),
                            format_func=label)
        dept_ids = [None, *dept_options]
        dept = c3.selectbox("Department", dept_ids,
                            index=dept_ids.index(e.get("department_id")),
                            format_func=lambda d: dept_options.get(d, "None"))
        c4, c5, c6 = st.columns(3)
        spec = c4.text_input("Specialization", e.get("specialization") or "")
        phone = c5.text_input("Phone", e.get("phone") or "")
        email = c6.text_input("Email", e.get("email") or "")
        c7, c8 = st.columns(2)
        joined = c7.date_input("Joining date",
                               clock.parse_date(e["joining_date"]) if e.get("joining_date")
                               else clock.today(), max_value=clock.today())
        status = c8.selectbox("Employment status", ["ACTIVE", "INACTIVE"],
                              index=0 if e.get("status", "ACTIVE") == "ACTIVE" else 1,
                              format_func=label)
        ok = st.form_submit_button("Save", type="primary")
    return ok, {"full_name": name, "role": role, "department_id": dept, "specialization": spec,
                "phone": phone, "email": email, "joining_date": joined, "status": status}


names = ["Directory", "Attendance", "Departments"] + (["Add staff"] if can_edit else [])
tabs = st.tabs(names)

with tabs[0]:
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    term = c1.text_input("Search name or code")
    role = c2.selectbox("Role", [None, *staff_service.STAFF_ROLES],
                        format_func=lambda r: label(r) if r else "All roles")
    dept = c3.selectbox("Department", [None, *dept_options],
                        format_func=lambda d: dept_options.get(d, "All departments"))
    status = c4.selectbox("Status", [None, "ACTIVE", "INACTIVE"],
                          format_func=lambda s: label(s) if s else "All")
    rows = staff_service.search(user, term, role, dept, status)
    st.caption(f"{len(rows)} staff member(s)")
    ui.table(ui.frame(rows, COLUMNS, code_cols=("role", "status")))

    if can_edit and rows:
        with st.expander("Edit a staff member"):
            sid = ui.select_id("Staff member", ui.option_map(
                rows, "staff_id", lambda r: f"{r['staff_code']} · {r['full_name']}"),
                key="edit_staff")
            if sid:
                ok, data = staff_form(f"edit_staff_{sid}", staff_service.get(user, sid))
                if ok:
                    ui.run_action(staff_service.update, user, sid, data,
                                  success="Staff member updated.")

with tabs[1]:
    day = st.date_input("Attendance date", clock.today(), max_value=clock.today())
    sheet = staff_service.attendance_sheet(user, day)
    marked = sum(1 for r in sheet if r["status"])
    st.caption(f"{marked} of {len(sheet)} active staff marked")
    ui.table(ui.frame(sheet, {"staff_code": "Code", "full_name": "Name", "role": "Role",
                              "status": "Attendance", "check_in": "In", "check_out": "Out",
                              "notes": "Notes"}, code_cols=("role", "status")))
    if ui.can(user, "attendance.edit") and sheet:
        with st.form("attendance", clear_on_submit=True):
            st.markdown("**Record attendance**")
            c1, c2, c3, c4 = st.columns(4)
            sid = c1.selectbox("Staff", [r["staff_id"] for r in sheet],
                               format_func=lambda i: next(r["full_name"] for r in sheet
                                                          if r["staff_id"] == i))
            status = c2.selectbox("Status", staff_service.ATTENDANCE_STATUSES, format_func=label)
            cin = c3.time_input("Check-in", None)
            cout = c4.time_input("Check-out", None)
            notes = st.text_input("Notes")
            if st.form_submit_button("Save attendance", type="primary"):
                ui.run_action(staff_service.mark_attendance, user, sid, day, status, cin, cout,
                              notes, success="Attendance saved.")

with tabs[2]:
    ui.table(ui.frame(departments, {"name": "Department", "description": "Description",
                                    "active_staff": "Active staff"}))
    if can_edit:
        with st.form("dept", clear_on_submit=True):
            st.markdown("**Add or rename a department**")
            target = st.selectbox("Department", [None, *dept_options],
                                  format_func=lambda d: dept_options.get(d, "➕ New department"))
            name = st.text_input("Name *")
            desc = st.text_input("Description")
            if st.form_submit_button("Save department", type="primary"):
                ui.run_action(staff_service.save_department, user, name, desc, target,
                              success="Department saved.")

if can_edit:
    with tabs[3]:
        ok, data = staff_form("new_staff")
        if ok:
            created = ui.run_action(staff_service.create, user, data, rerun=False)
            if created:
                ui.flash("success", f"Added {created['full_name']} ({created['staff_code']}).")
                st.rerun()
