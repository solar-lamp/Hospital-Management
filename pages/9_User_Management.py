import streamlit as st

from services import audit_service, auth_service, staff_service
from utils import ui
from utils.permissions import PERMISSIONS, ROLE_LABELS, ROLES

user = ui.require_page("users.manage")

st.title("User Management")
ui.show_flash()

users = auth_service.list_users(user)
staff = staff_service.staff_options(user)
staff_map = {s["staff_id"]: f"{s['staff_code']} · {s['full_name']}" for s in staff}

tabs = st.tabs(["Users", "Add user", "Roles & permissions", "Audit log"])

with tabs[0]:
    ui.table(ui.frame([{**u, "role": ROLE_LABELS[u["role"]],
                        "active": "Yes" if u["active"] else "No"} for u in users],
                      {"username": "Username", "full_name": "Name", "role": "Role",
                       "staff_name": "Linked staff", "active": "Active",
                       "last_login_at": "Last login"}))
    umap = {u["user_id"]: f"{u['username']} · {u['full_name']}" for u in users}
    uid = st.selectbox("Edit user", list(umap), format_func=umap.get, index=None)
    if uid:
        e = next(u for u in users if u["user_id"] == uid)
        with st.form(f"user_{uid}"):
            c1, c2, c3 = st.columns(3)
            name = c1.text_input("Full name", e["full_name"])
            role = c2.selectbox("Role", ROLES, index=ROLES.index(e["role"]),
                                format_func=ROLE_LABELS.get)
            sids = [None, *staff_map]
            sid = c3.selectbox("Linked staff", sids,
                               index=sids.index(e["staff_id"]) if e["staff_id"] in sids else 0,
                               format_func=lambda s: staff_map.get(s, "None"),
                               help="Doctors must be linked to their staff record to see "
                                    "their own appointments.")
            active = st.checkbox("Active", bool(e["active"]))
            if st.form_submit_button("Save user", type="primary"):
                ui.run_action(auth_service.update_user, user, uid, name, role, sid, active,
                              success="User updated.")
        with st.form(f"reset_{uid}", clear_on_submit=True):
            pw = st.text_input("New password", type="password")
            if st.form_submit_button("Reset password"):
                ui.run_action(auth_service.reset_password, user, uid, pw,
                              success="Password reset.")

with tabs[1]:
    with st.form("new_user", clear_on_submit=True):
        c1, c2 = st.columns(2)
        username = c1.text_input("Username *")
        name = c2.text_input("Full name *")
        c3, c4 = st.columns(2)
        role = c3.selectbox("Role *", ROLES, format_func=ROLE_LABELS.get)
        sid = c4.selectbox("Linked staff", [None, *staff_map],
                           format_func=lambda s: staff_map.get(s, "None"))
        pw = st.text_input("Initial password *", type="password",
                           help="At least 8 characters mixing letters with digits or symbols.")
        if st.form_submit_button("Create user", type="primary"):
            ui.run_action(auth_service.create_user, user, username, name, pw, role, sid,
                          success="User created.")

with tabs[2]:
    st.caption("Permissions are enforced in the service layer; navigation only hides pages.")
    matrix = [{"Permission": p, **{ROLE_LABELS[r]: "✓" if r in roles else "" for r in ROLES}}
              for p, roles in PERMISSIONS.items()]
    st.dataframe(matrix, hide_index=True, width="stretch")

with tabs[3]:
    st.caption("Append-only: the database rejects edits and deletions of audit entries.")
    entity = st.selectbox("Entity", [None, "patient", "staff", "appointment", "admission", "bed",
                                     "batch", "medicine", "purchase", "bill", "payment", "user",
                                     "system"], format_func=lambda e: e or "All")
    rows = audit_service.recent(user, 300, entity)
    ui.table(ui.frame(rows, {"created_at": "When", "username": "User", "action": "Action",
                             "entity_type": "Entity", "entity_id": "ID",
                             "description": "Details"}), empty="No audit entries.")
