import tempfile
from pathlib import Path

import streamlit as st

import config
import database
from services import auth_service
from utils import clock, ui
from utils.permissions import ROLE_LABELS

user = ui.require_page("dashboard.view")

st.title("Settings & About")
ui.show_flash()

st.subheader("My account")
st.write(f"Signed in as **{user['full_name']}** (`{user['username']}`), "
         f"{ROLE_LABELS[user['role']]}. Last login: {user['last_login_at'] or '—'}")
with st.form("own_password", clear_on_submit=True):
    st.markdown("**Change password**")
    current = st.text_input("Current password", type="password")
    new = st.text_input("New password", type="password")
    confirm = st.text_input("Confirm new password", type="password")
    if st.form_submit_button("Change password"):
        if new != confirm:
            st.error("New passwords do not match.")
        else:
            ui.run_action(auth_service.change_own_password, user, current, new,
                          success="Password changed.")

if ui.can(user, "system.backup"):
    st.divider()
    st.subheader("Backup and restore")
    st.caption("Backups use SQLite's online backup API, so they are consistent even while "
               "the app is running. Store backups securely: they contain all records.")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("Download database backup", database.backup_bytes(),
                           f"meditrack_backup_{clock.now():%Y%m%d_%H%M%S}.db",
                           "application/octet-stream", width="stretch")
        if not config.demo_mode() and st.button("Save backup to server folder",
                                                 width="stretch"):
            dest = config.get_backup_dir() / f"hospital_{clock.now():%Y%m%d_%H%M%S}.db"
            database.backup_to(dest)
            st.success(f"Saved {dest}")
    with c2:
        upload = st.file_uploader("Restore from a backup file", type=["db", "sqlite"])
        if upload is not None:
            st.warning("Restoring replaces ALL current data with the backup.")
            if st.button("Restore now", type="primary"):
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / "restore.db"
                    path.write_bytes(upload.getvalue())
                    try:
                        database.restore_from(path)
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        ui.logout()
                        ui.flash("success", "Backup restored. Please log in again.")
                        st.rerun()

    if config.demo_mode():
        st.divider()
        st.subheader("Demo data")
        st.caption("Deletes everything stored in this browser and recreates the fictional "
                   "demo data with dates relative to today.")
        if st.button("Reset demo data"):
            import seed
            with st.spinner("Rebuilding demo data..."):
                seed.reset_demo()
            ui.logout()
            ui.flash("success", "Demo data reset. Please log in again.")
            st.rerun()

st.divider()
st.subheader("About")
st.markdown(f"""
**{config.APP_TITLE}**

An educational hospital management prototype built with Python, Streamlit and SQLite.
Layers: Streamlit pages → service layer (validation, permissions, transactions) →
repositories (parameterized SQL) → SQLite.

* Schema version: **{database.init_db()}**
* Expiry warning window: **{config.EXPIRY_WARNING_DAYS} days** (today inclusive)
* Low stock: usable (non-expired) stock **≤** reorder level
* Session idle timeout: **{config.SESSION_TIMEOUT_MINUTES // 60} hours**
* Timestamps: local time, `YYYY-MM-DD HH:MM:SS`

**Limitations:** not a clinically certified system. Use synthetic data only. SQLite suits a
single-instance prototype; a production multi-user deployment would need PostgreSQL, HTTPS,
a security and privacy review, and managed backups.
""")
