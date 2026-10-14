from datetime import timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
from services import report_service
from utils import charts, clock, ui
from utils.formatting import from_minor, label, money

user = ui.require_page("dashboard.view")

st.title("Dashboard")
st.caption(f"{clock.today():%A, %d %B %Y} · all figures are live from the database")
ui.show_flash()

m = report_service.dashboard_metrics(user)

row1 = st.columns(4)
row1[0].metric("Registered patients", m["patients_total"],
               help=f"{m['patients_active']} active, {m['patients_total'] - m['patients_active']} archived")
row1[1].metric("Active staff", m["staff_active"])
row1[2].metric("Appointments today", m["appointments_today"],
               help="Scheduled, confirmed or completed; cancelled and no-shows excluded")
row1[3].metric("Current admissions", m["admissions_current"])

row2 = st.columns(4)
row2[0].metric("Beds available", m["beds_available"],
               help=f"{m['beds_occupied']} occupied, {m['beds_out_of_service']} out of service")
row2[1].metric("Medicines in stock", m["medicines_in_stock"],
               help="Medicines with at least one non-expired batch in stock")
row2[2].metric("Low-stock alerts", m["low_stock"],
               help="Active medicines whose usable stock is at or below the reorder level")
row2[3].metric(f"Expiring ≤ {config.EXPIRY_WARNING_DAYS} days", m["expiring_batches"],
               help="Batches with stock expiring from today onwards within the warning period")

row3 = st.columns(3)
row3[0].metric("Billed this month", money(m["billed_month"]))
row3[1].metric("Collected this month", money(m["collected_month"]))
row3[2].metric("Outstanding balance", money(m["outstanding"]),
               help="Final bill totals minus accepted payments (all time)")

st.divider()
data = report_service.dashboard_charts(user)

c1, c2 = st.columns(2)
with c1:
    st.subheader("Appointments by day")
    df = data["appointments"]
    if df.empty:
        st.info("No appointments in this period.")
    else:
        order = [s for s in charts.STATUS_COLORS if s in set(df["status"])]
        fig = px.bar(df, x="day", y="appointments", color="status",
                     category_orders={"status": order}, color_discrete_map=charts.STATUS_COLORS,
                     labels={"day": "Day", "appointments": "Appointments", "status": "Status"})
        fig.for_each_trace(lambda t: t.update(name=label(t.name)))
        st.plotly_chart(charts.style(fig), width="stretch")
        st.caption("Past 14 days and next 7 days")

with c2:
    st.subheader("Bed occupancy by ward")
    df = data["occupancy"]
    if df.empty:
        st.info("No wards configured yet.")
    else:
        fig = go.Figure()
        for col, name, color in (("occupied", "Occupied", charts.PALETTE[0]),
                                 ("available", "Available", charts.PALETTE[2]),
                                 ("out_of_service", "Out of service", charts.PALETTE[3])):
            fig.add_bar(y=df["ward"], x=df[col], name=name, orientation="h",
                        marker_color=color)
        fig = charts.style(fig)
        fig.update_layout(barmode="stack", hovermode="y unified", legend_traceorder="normal")
        fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch")

c3, c4 = st.columns(2)
with c3:
    st.subheader("Admissions and discharges")
    df = data["flow"]
    if df.empty:
        st.info("No admissions in the last 30 days.")
    else:
        days = pd.date_range(clock.today() - timedelta(days=29), clock.today())
        df = (df.assign(day=pd.to_datetime(df["day"])).set_index("day")
              .reindex(days, fill_value=0).rename_axis("day").reset_index())
        fig = go.Figure()
        fig.add_scatter(x=df["day"], y=df["admissions"], name="Admissions", mode="lines",
                        line=dict(color=charts.PALETTE[0], width=2))
        fig.add_scatter(x=df["day"], y=df["discharges"], name="Discharges", mode="lines",
                        line=dict(color=charts.PALETTE[1], width=2))
        st.plotly_chart(charts.style(fig), width="stretch")
        st.caption("Last 30 days")

with c4:
    st.subheader("Billed vs collected by month")
    df = data["billing"]
    if df.empty:
        st.info("No billing activity yet.")
    else:
        fig = go.Figure()
        fig.add_bar(x=df["month"], y=df["billed_minor"].map(from_minor).astype(float),
                    name="Billed", marker_color=charts.PALETTE[0])
        fig.add_bar(x=df["month"], y=df["collected_minor"].map(from_minor).astype(float),
                    name="Collected", marker_color=charts.PALETTE[2])
        fig.update_layout(barmode="group")
        fig = charts.style(fig, y_title=config.CURRENCY_SYMBOL)
        fig.update_xaxes(type="category")
        st.plotly_chart(fig, width="stretch")

st.subheader("Usable medicine stock by category")
df = data["stock"]
if df.empty:
    st.info("No medicine stock recorded.")
else:
    fig = px.bar(df, x="units", y="category", orientation="h",
                 labels={"units": "Units in stock", "category": "Category"},
                 color_discrete_sequence=[charts.PALETTE[0]])
    fig = charts.style(fig, height=300)
    fig.update_layout(hovermode="closest")
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")

st.divider()
recent = report_service.recent_activity(user)
a, b = st.columns(2)
if "appointments" in recent:
    with a:
        st.subheader("Today's appointments")
        rows = [{**r, "time": r["start_at"][11:16]} for r in recent["appointments"]]
        ui.table(ui.frame(rows, {"time": "Time", "patient_code": "Patient",
                                 "doctor_name": "Doctor", "status": "Status"},
                          code_cols=("status",)), empty="No appointments today.")
if "payments" in recent:
    with b:
        st.subheader("Recent payments")
        ui.table(ui.frame(recent["payments"],
                          {"paid_at": "Paid at", "bill_number": "Bill", "amount_minor": "Amount",
                           "method": "Method", "status": "Status"},
                          money_cols=("amount_minor",), code_cols=("status",)),
                 money=("Amount",), empty="No payments yet.")
if "low_stock" in recent:
    with a:
        st.subheader("Low-stock medicines")
        ui.table(ui.frame(recent["low_stock"], {"name": "Medicine", "strength": "Strength",
                                                "usable_stock": "Usable stock",
                                                "reorder_level": "Reorder level"}),
                 empty="No low-stock medicines.")
    with b:
        st.subheader("Expiring soon")
        ui.table(ui.frame(recent["expiring"], {"medicine": "Medicine", "batch_number": "Batch",
                                               "expiry_date": "Expiry",
                                               "quantity_on_hand": "Quantity"}),
                 empty="No batches expiring soon.")
