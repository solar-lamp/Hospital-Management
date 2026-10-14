import streamlit as st

from services import pharmacy_service
from utils import ui
from utils.formatting import label

user = ui.require_page("suppliers.view")
can_edit = ui.can(user, "suppliers.edit")

st.title("Suppliers & Purchases")
ui.show_flash()

suppliers = pharmacy_service.list_suppliers(user)
sup_map = {s["supplier_id"]: s["name"] for s in suppliers}
tabs = st.tabs(["Suppliers", "Purchase receipts"])

with tabs[0]:
    ui.table(ui.frame(suppliers, {"name": "Supplier", "contact_person": "Contact",
                                  "phone": "Phone", "email": "Email", "address": "Address",
                                  "status": "Status", "purchases": "Receipts"},
                      code_cols=("status",)), empty="No suppliers yet.")
    if can_edit:
        target = st.selectbox("Add or edit", [None, *sup_map],
                              format_func=lambda s: sup_map.get(s, "➕ New supplier"))
        e = next((s for s in suppliers if s["supplier_id"] == target), {})
        with st.form(f"supplier_{target}", clear_on_submit=target is None):
            c1, c2 = st.columns(2)
            name = c1.text_input("Name *", e.get("name", ""))
            contact = c2.text_input("Contact person", e.get("contact_person") or "")
            c3, c4 = st.columns(2)
            phone = c3.text_input("Phone", e.get("phone") or "")
            email = c4.text_input("Email", e.get("email") or "")
            address = st.text_input("Address", e.get("address") or "")
            status = st.selectbox("Status", ["ACTIVE", "INACTIVE"], format_func=label,
                                  index=0 if e.get("status", "ACTIVE") == "ACTIVE" else 1)
            if st.form_submit_button("Save supplier", type="primary"):
                ui.run_action(pharmacy_service.save_supplier, user,
                              {"name": name, "contact_person": contact, "phone": phone,
                               "email": email, "address": address, "status": status}, target,
                              success="Supplier saved.")

with tabs[1]:
    start, end = ui.date_range("pur", default_days=90)
    sid = st.selectbox("Supplier", [None, *sup_map], format_func=lambda s: sup_map.get(s, "All"))
    rows = pharmacy_service.purchases(user, sid, start, end)
    df = ui.frame(rows, {"purchase_id": "Receipt", "received_date": "Received",
                         "supplier": "Supplier", "invoice_reference": "Invoice",
                         "medicine": "Medicine", "batch_number": "Batch", "expiry_date": "Expiry",
                         "quantity": "Quantity", "unit_cost_minor": "Unit cost",
                         "line_cost_minor": "Line cost"},
                  money_cols=("unit_cost_minor", "line_cost_minor"))
    ui.table(df, money=("Unit cost", "Line cost"), empty="No purchase receipts in this period.")
    if not df.empty:
        st.metric("Total purchase cost", f"₹{df['Line cost'].sum():,.2f}")
    if ui.can(user, "pharmacy.edit"):
        st.caption("Record new receipts from Pharmacy & Medicines → Receive stock.")
