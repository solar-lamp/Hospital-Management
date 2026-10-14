import streamlit as st

import config
from services import pharmacy_service
from services.pharmacy_service import ReceiptLine
from utils import clock, ui
from utils.formatting import label, to_minor

user = ui.require_page("pharmacy.view")
can_edit = ui.can(user, "pharmacy.edit")

st.title("Pharmacy & Medicines")
st.caption("Stock is tracked per batch. Issues use first-expiry-first-out and never include "
           "expired batches. Tracking issues does not validate treatment or prescriptions.")
ui.show_flash()

alerts = pharmacy_service.alerts(user)
c = st.columns(3)
c[0].metric("Low-stock medicines", len(alerts["low_stock"]))
c[1].metric(f"Batches expiring ≤ {config.EXPIRY_WARNING_DAYS} days", len(alerts["near_expiry"]))
c[2].metric("Expired batches with stock", len(alerts["expired"]))

names = ["Stock", "Batches", "Alerts"]
if can_edit:
    names += ["Receive stock", "Issue / return / adjust", "Catalogue"]
names.append("Movement history")
tabs = dict(zip(names, st.tabs(names)))

meds = pharmacy_service.medicine_options(user, active_only=False)
med_map = ui.option_map(meds, "medicine_id",
                        lambda m: f"{m['name']} {m['strength'] or ''} {m['form'] or ''}".strip())
active_med_map = ui.option_map(pharmacy_service.medicine_options(user), "medicine_id",
                               lambda m: med_map[m["medicine_id"]])

with tabs["Stock"]:
    term = st.text_input("Search medicine or generic name")
    rows = pharmacy_service.stock_summary(user, term)
    for r in rows:
        r["alert"] = "⚠️ Low" if r["low_stock"] else ""
    ui.table(ui.frame(rows, {"name": "Medicine", "generic_name": "Generic", "strength": "Strength",
                             "form": "Form", "category": "Category", "usable_stock": "Usable stock",
                             "unit": "Unit", "reorder_level": "Reorder level",
                             "alert": "Alert", "next_expiry": "Next expiry",
                             "expired_stock": "Expired stock"}),
             empty="No medicines found.")
    st.caption("Usable stock counts only non-expired batches. Low stock means usable stock "
               "is at or below (≤) the reorder level.")

BATCH_COLS = {"medicine": "Medicine", "strength": "Strength", "batch_number": "Batch",
              "expiry_date": "Expiry", "quantity_on_hand": "Quantity",
              "purchase_price_minor": "Cost", "selling_price_minor": "Price",
              "supplier": "Supplier"}

with tabs["Batches"]:
    c1, c2 = st.columns([2, 1])
    mid = c1.selectbox("Medicine", [None, *med_map], format_func=lambda m: med_map.get(m, "All"))
    in_stock = c2.checkbox("Only batches with stock", True)
    rows = pharmacy_service.batches(user, mid, in_stock_only=in_stock)
    today = clock.ds()
    for r in rows:
        r["state"] = "Expired" if r["expiry_date"] < today else "Usable"
    ui.table(ui.frame(rows, {**BATCH_COLS, "state": "State"},
                      money_cols=("purchase_price_minor", "selling_price_minor")),
             money=("Cost", "Price"), empty="No batches.")

with tabs["Alerts"]:
    st.subheader("Low stock")
    ui.table(ui.frame(alerts["low_stock"], {"name": "Medicine", "strength": "Strength",
                                            "usable_stock": "Usable stock",
                                            "reorder_level": "Reorder level"}),
             empty="No medicines are low on stock.")
    st.subheader(f"Expiring within {config.EXPIRY_WARNING_DAYS} days (today included)")
    ui.table(ui.frame(alerts["near_expiry"], BATCH_COLS,
                      money_cols=("purchase_price_minor", "selling_price_minor")),
             money=("Cost", "Price"), empty="No batches are near expiry.")
    st.subheader("Expired batches still holding stock")
    ui.table(ui.frame(alerts["expired"], BATCH_COLS,
                      money_cols=("purchase_price_minor", "selling_price_minor")),
             money=("Cost", "Price"), empty="No expired stock.")
    if alerts["expired"]:
        st.caption("Dispose of expired stock with a negative adjustment so the movement "
                   "history records why it left inventory.")

if can_edit:
    with tabs["Receive stock"]:
        suppliers = pharmacy_service.list_suppliers(user, active_only=True) \
            if ui.can(user, "suppliers.view") else []
        sup_map = {s["supplier_id"]: s["name"] for s in suppliers}
        with st.form("receive", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                sid = ui.select_id("Supplier *", sup_map)
            rdate = c2.date_input("Received date", clock.today(), max_value=clock.today())
            invoice = c3.text_input("Invoice reference")
            c4, c5, c6 = st.columns(3)
            with c4:
                mid = ui.select_id("Medicine *", active_med_map)
            batch = c5.text_input("Batch number *")
            expiry = c6.date_input("Expiry date *", None, min_value=clock.today())
            c7, c8, c9 = st.columns(3)
            qty = c7.number_input("Quantity *", min_value=1, step=1, value=1)
            cost = c8.number_input("Unit cost (₹)", min_value=0.0, step=0.5)
            price = c9.number_input("Selling price (₹)", min_value=0.0, step=0.5)
            ok = st.form_submit_button("Receive stock", type="primary")
        if ok:
            if not (sid and mid and expiry):
                st.error("Supplier, medicine and expiry date are required.")
            else:
                line = ReceiptLine(mid, batch, expiry, int(qty), to_minor(cost),
                                   to_minor(price) if price else None)
                ui.run_action(pharmacy_service.receive_stock, user, sid, rdate, invoice, [line],
                              success="Stock received and receipt movement recorded.")
        st.caption("If the batch number already exists for the medicine, its expiry must "
                   "match and the quantity is added to that batch.")

    with tabs["Issue / return / adjust"]:
        mode = st.radio("Operation", ["Issue (FEFO)", "Issue from a batch", "Return", "Adjust"],
                        horizontal=True)
        if mode == "Issue (FEFO)":
            with st.form("fefo", clear_on_submit=True):
                mid = ui.select_id("Medicine *", active_med_map)
                c1, c2 = st.columns(2)
                qty = c1.number_input("Quantity *", min_value=1, step=1, value=1)
                ref = c2.text_input("Reference (ward / patient code)")
                reason = st.text_input("Reason *", "Ward issue")
                ok = st.form_submit_button("Issue", type="primary")
            if ok:
                taken = ui.run_action(pharmacy_service.issue_fefo, user, mid, int(qty), reason,
                                      ref, rerun=False)
                if taken:
                    ui.flash("success", "Issued " + ", ".join(f"{q} from {b}" for b, q in taken))
                    st.rerun()
        else:
            usable_only = mode == "Issue from a batch"
            batch_rows = pharmacy_service.batches(user, in_stock_only=(mode != "Return"),
                                                  usable_only=usable_only)
            bmap = {b["batch_id"]: f"{b['medicine']} {b['strength'] or ''} · {b['batch_number']}"
                                   f" · exp {b['expiry_date']} · qty {b['quantity_on_hand']}"
                    for b in batch_rows}
            with st.form("batch_op", clear_on_submit=True):
                bid = ui.select_id("Batch *", bmap)
                if mode == "Adjust":
                    qty = st.number_input("Quantity change (negative to remove) *", step=1,
                                          value=0)
                else:
                    qty = st.number_input("Quantity *", min_value=1, step=1, value=1)
                reason = st.text_input("Reason *")
                ref = st.text_input("Reference") if mode != "Adjust" else None
                ok = st.form_submit_button(mode, type="primary")
            if ok:
                if not bid:
                    st.error("Select a batch.")
                elif mode == "Issue from a batch":
                    ui.run_action(pharmacy_service.issue_from_batch, user, bid, int(qty), reason,
                                  ref, success="Stock issued.")
                elif mode == "Return":
                    ui.run_action(pharmacy_service.return_to_stock, user, bid, int(qty), reason,
                                  ref, success="Return recorded.")
                else:
                    ui.run_action(pharmacy_service.adjust_stock, user, bid, int(qty), reason,
                                  success="Adjustment recorded.")

    with tabs["Catalogue"]:
        target = st.selectbox("Medicine", [None, *med_map],
                              format_func=lambda m: med_map.get(m, "➕ New medicine"))
        e = next((m for m in pharmacy_service.stock_summary(user) if m["medicine_id"] == target),
                 {}) if target else {}
        with st.form(f"medicine_{target}", clear_on_submit=target is None):
            c1, c2, c3 = st.columns(3)
            name = c1.text_input("Name *", e.get("name", ""))
            generic = c2.text_input("Generic name", e.get("generic_name") or "")
            strength = c3.text_input("Strength", e.get("strength") or "")
            c4, c5, c6 = st.columns(3)
            forms = list(pharmacy_service.FORMS)
            form = c4.selectbox("Form", forms,
                                index=forms.index(e["form"]) if e.get("form") in forms else 0)
            category = c5.text_input("Category", e.get("category") or "")
            unit = c6.text_input("Unit", e.get("unit") or "tablet")
            c7, c8 = st.columns(2)
            reorder = c7.number_input("Reorder level", min_value=0, step=1,
                                      value=int(e.get("reorder_level", 10)))
            active = c8.checkbox("Active", bool(e.get("active", 1)))
            ok = st.form_submit_button("Save medicine", type="primary")
        if ok:
            ui.run_action(pharmacy_service.save_medicine, user,
                          {"name": name, "generic_name": generic, "strength": strength,
                           "form": form, "category": category, "unit": unit,
                           "reorder_level": int(reorder), "active": active}, target,
                          success="Medicine saved.")

with tabs["Movement history"]:
    start, end = ui.date_range("mov", default_days=30)
    c1, c2 = st.columns(2)
    mid = c1.selectbox("Medicine", [None, *med_map], format_func=lambda m: med_map.get(m, "All"),
                       key="mov_med")
    mtype = c2.selectbox("Type", [None, *pharmacy_service.MOVEMENT_TYPES],
                         format_func=lambda t: label(t) if t else "All")
    rows = pharmacy_service.movements(user, start, end, mid, mtype)
    ui.table(ui.frame(rows, {"created_at": "When", "medicine": "Medicine", "batch_number": "Batch",
                             "movement_type": "Type", "quantity_delta": "Change",
                             "reason": "Reason", "reference": "Reference",
                             "username": "By"}, code_cols=("movement_type",)),
             empty="No stock movements in this period.")
    mismatches = pharmacy_service.reconciliation_mismatches(user)
    if mismatches:
        st.error(f"{len(mismatches)} batch(es) do not reconcile with their movement history.")
    else:
        st.success("All batch quantities reconcile with their movement history.")
