import pandas as pd
import streamlit as st

from services import billing_service, patient_service
from services.billing_service import BillLine
from utils import clock, ui
from utils.formatting import label, money, to_minor
from utils.validators import ValidationError

user = ui.require_page("billing.view")
can_edit = ui.can(user, "billing.edit")

st.title("Billing & Payments")
st.caption("Amounts are stored in paise. Balance = bill total − accepted payments. "
           "Bills and payments are voided, never deleted.")
ui.show_flash()

BILL_COLS = {"bill_number": "Bill", "bill_date": "Date", "patient_code": "Patient code",
             "patient_name": "Patient", "total_minor": "Total", "paid_minor": "Paid",
             "balance_minor": "Balance", "status": "Status"}
MONEY = ("total_minor", "paid_minor", "balance_minor")

names = ["Bills"] + (["Create bill"] if can_edit else []) + ["Bill details", "Payments"]
tabs = dict(zip(names, st.tabs(names)))

with tabs["Bills"]:
    start, end = ui.date_range("bills", default_days=60)
    c1, c2 = st.columns(2)
    status = c1.selectbox("Status", [None, "FINAL", "VOID"],
                          format_func=lambda s: label(s) if s else "All")
    outstanding = c2.checkbox("Only bills with an outstanding balance")
    rows = billing_service.search(user, start, end, status=status, outstanding_only=outstanding)
    df = ui.frame(rows, BILL_COLS, money_cols=MONEY, code_cols=("status",))
    ui.table(df, money=("Total", "Paid", "Balance"), empty="No bills match the filters.")
    if rows:
        valid = [r for r in rows if r["status"] == "FINAL"]
        c = st.columns(3)
        c[0].metric("Billed", money(sum(r["total_minor"] for r in valid)))
        c[1].metric("Paid", money(sum(r["paid_minor"] for r in valid)))
        c[2].metric("Outstanding", money(sum(r["balance_minor"] for r in valid)))

if can_edit:
    with tabs["Create bill"]:
        patients = ui.option_map(patient_service.options(user, active_only=False), "patient_id",
                                 lambda p: f"{p['patient_code']} · {p['full_name']}")
        pid = ui.select_id("Patient *", patients, key="bill_patient")
        if pid:
            ctx = billing_service.billable_context(user, pid)
            adm_map = {a["admission_id"]: f"Admission {a['admitted_at'][:10]} · {a['bed_code']}"
                                          f" ({label(a['status'])})" for a in ctx["admissions"]}
            appt_map = {a["appointment_id"]: f"{a['start_at'][:16]} · {a['doctor_name']}"
                                             f" ({label(a['status'])})"
                        for a in ctx["appointments"]}
            c1, c2, c3 = st.columns(3)
            adm = c1.selectbox("Link to admission", [None, *adm_map],
                               format_func=lambda a: adm_map.get(a, "None"))
            appt = c2.selectbox("Link to appointment", [None, *appt_map],
                                format_func=lambda a: appt_map.get(a, "None"))
            bill_date = c3.date_input("Bill date", clock.today(), max_value=clock.today())

            st.markdown("**Items**")
            version = st.session_state.setdefault("bill_editor_version", 0)
            items = st.data_editor(
                pd.DataFrame({"Description": ["Consultation fee"], "Quantity": [1],
                              "Unit price (₹)": [500.0]}),
                num_rows="dynamic", width="stretch", key=f"bill_items_{version}",
                column_config={
                    "Quantity": st.column_config.NumberColumn(min_value=1, step=1, format="%d"),
                    "Unit price (₹)": st.column_config.NumberColumn(min_value=0.0, step=0.5,
                                                                    format="%.2f")})
            c4, c5 = st.columns(2)
            discount = c4.number_input("Discount (₹)", min_value=0.0, step=10.0)
            tax_pct = c5.number_input("Tax (%)", min_value=0.0, max_value=100.0, step=0.5)
            notes = st.text_input("Notes")

            lines, error = [], None
            try:
                for _, r in items.dropna(how="all").iterrows():
                    if pd.isna(r["Quantity"]) or pd.isna(r["Unit price (₹)"]):
                        raise ValidationError("Every item needs a quantity and unit price.")
                    lines.append(BillLine(str(r["Description"] or ""), int(r["Quantity"]),
                                          to_minor(r["Unit price (₹)"])))
                calc = billing_service.calculate(lines, to_minor(discount),
                                                 int(round(tax_pct * 100)))
            except ValidationError as exc:
                error, calc = str(exc), None
            if calc:
                t = st.columns(4)
                t[0].metric("Subtotal", money(calc["subtotal"]))
                t[1].metric("Discount", money(calc["discount"]))
                t[2].metric("Tax", money(calc["tax"]))
                t[3].metric("Total", money(calc["total"]))
            else:
                st.warning(error)
            if st.button("Create bill", type="primary", disabled=calc is None):
                bill = ui.run_action(billing_service.create_bill, user, pid, lines,
                                     discount_minor=to_minor(discount),
                                     tax_basis_points=int(round(tax_pct * 100)),
                                     bill_date=bill_date, admission_id=adm, appointment_id=appt,
                                     notes=notes, rerun=False)
                if bill:
                    st.session_state["bill_editor_version"] = version + 1
                    st.session_state["bill_detail"] = bill["bill_id"]
                    ui.flash("success", f"Created {bill['bill_number']} for {money(bill['total_minor'])}.")
                    st.rerun()

with tabs["Bill details"]:
    all_bills = billing_service.search(user)
    bill_map = {b["bill_id"]: f"{b['bill_number']} · {b['patient_name']} · "
                              f"{money(b['total_minor'])} ({label(b['status'])})" for b in all_bills}
    default = st.session_state.get("bill_detail")
    bid = st.selectbox("Bill", list(bill_map), format_func=bill_map.get,
                       index=list(bill_map).index(default) if default in bill_map else None,
                       placeholder="Select a bill")
    if bid:
        bill = billing_service.get_bill(user, bid)
        st.subheader(f"{bill['bill_number']} — {bill['patient_name']} ({bill['patient_code']})")
        st.caption(f"Date {bill['bill_date']} · Status {label(bill['status'])}"
                   + (f" · Void reason: {bill['void_reason']}" if bill["void_reason"] else "")
                   + (f" · {bill['notes']}" if bill["notes"] else ""))
        ui.table(ui.frame(bill["items"], {"description": "Item", "quantity": "Qty",
                                          "unit_price_minor": "Unit price",
                                          "line_total_minor": "Line total"},
                          money_cols=("unit_price_minor", "line_total_minor")),
                 money=("Unit price", "Line total"))
        m = st.columns(5)
        m[0].metric("Subtotal", money(bill["subtotal_minor"]))
        m[1].metric("Discount", money(bill["discount_minor"]))
        m[2].metric("Tax", money(bill["tax_minor"]))
        m[3].metric("Total", money(bill["total_minor"]))
        m[4].metric("Balance due", money(bill["balance_minor"]))

        st.markdown("**Payments**")
        ui.table(ui.frame(bill["payments"], {"payment_id": "ID", "paid_at": "Paid at",
                                             "amount_minor": "Amount", "method": "Method",
                                             "reference": "Reference", "status": "Status",
                                             "void_reason": "Void reason",
                                             "recorded_by_user": "Recorded by"},
                          money_cols=("amount_minor",), code_cols=("method", "status")),
                 money=("Amount",), empty="No payments recorded.")

        if can_edit and bill["status"] == "FINAL":
            if bill["balance_minor"] > 0:
                with st.form(f"pay_{bid}", clear_on_submit=True):
                    st.markdown("**Record payment**")
                    c1, c2, c3 = st.columns(3)
                    amount = c1.number_input("Amount (₹)", min_value=0.01,
                                             max_value=bill["balance_minor"] / 100,
                                             value=bill["balance_minor"] / 100, step=50.0)
                    method = c2.selectbox("Method", billing_service.PAYMENT_METHODS,
                                          format_func=label)
                    ref = c3.text_input("Reference")
                    if st.form_submit_button("Record payment", type="primary"):
                        ui.run_action(billing_service.record_payment, user, bid, to_minor(amount),
                                      method, ref, success="Payment recorded.")
            accepted = {p["payment_id"]: f"#{p['payment_id']} {money(p['amount_minor'])}"
                        for p in bill["payments"] if p["status"] == "ACCEPTED"}
            with st.expander("Corrections (void)"):
                if accepted:
                    with st.form(f"void_pay_{bid}"):
                        pay = st.selectbox("Payment", list(accepted), format_func=accepted.get)
                        why = st.text_input("Reason *")
                        if st.form_submit_button("Void payment"):
                            ui.run_action(billing_service.void_payment, user, pay, why,
                                          success="Payment voided.")
                with st.form(f"void_bill_{bid}"):
                    why = st.text_input("Reason for voiding the bill *")
                    if st.form_submit_button("Void bill", disabled=bool(accepted)):
                        ui.run_action(billing_service.void_bill, user, bid, why,
                                      success="Bill voided.")
                    if accepted:
                        st.caption("Void the accepted payments before voiding the bill.")

with tabs["Payments"]:
    start, end = ui.date_range("pay", default_days=30)
    rows = billing_service.payments(user, start, end)
    df = ui.frame(rows, {"payment_id": "ID", "paid_at": "Paid at", "bill_number": "Bill",
                         "patient_name": "Patient", "amount_minor": "Amount", "method": "Method",
                         "reference": "Reference", "status": "Status",
                         "recorded_by": "Recorded by"},
                  money_cols=("amount_minor",), code_cols=("method", "status"))
    ui.table(df, money=("Amount",), empty="No payments in this period.")
    if rows:
        st.metric("Accepted payments", money(sum(r["amount_minor"] for r in rows
                                                 if r["status"] == "ACCEPTED")))
