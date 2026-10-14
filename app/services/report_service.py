"""Dashboard metrics and filtered reports. Every number comes from SQL.

Metric definitions (also in README):
* Total patients        - all patient records; active shown separately.
* Active staff          - staff with status ACTIVE.
* Today's appointments  - appointments starting today, status scheduled,
                          confirmed or completed (cancelled/no-show excluded).
* Current admissions    - admissions with status ADMITTED.
* Occupied beds         - beds with an ADMITTED admission.
* Available beds        - operational (AVAILABLE) beds with no active admission.
* Medicines in stock    - medicines with at least one non-expired batch > 0.
* Low-stock medicines   - active medicines whose usable stock <= reorder level.
* Expiring batches      - positive-stock batches expiring today .. today+N days.
* Total billed          - sum of FINAL bills dated in the period.
* Payments received     - sum of ACCEPTED payments made in the period.
* Outstanding balance   - FINAL bill totals minus their accepted payments.
"""

from datetime import date, timedelta

import pandas as pd

import config
from database import read_connection
from repositories import (admission_repository, appointment_repository, billing_repository,
                          patient_repository, pharmacy_repository, report_repository,
                          staff_repository)
from utils import clock
from utils.permissions import has_permission, require


def dashboard_metrics(user) -> dict:
    require(user, "dashboard.view")
    today = clock.today()
    month_start = today.replace(day=1)
    with read_connection() as conn:
        occupancy = admission_repository.occupancy_by_ward(conn)
        summary = pharmacy_repository.stock_summary(conn, today.isoformat(), active_only=True)
        billed, collected = billing_repository.totals(conn, month_start.isoformat(),
                                                      today.isoformat())
        return {
            "patients_total": patient_repository.count(conn),
            "patients_active": patient_repository.count(conn, "ACTIVE"),
            "staff_active": staff_repository.count_active(conn),
            "appointments_today": appointment_repository.count_on(conn, today.isoformat()),
            "admissions_current": admission_repository.count_active(conn),
            "beds_occupied": sum(r["occupied"] or 0 for r in occupancy),
            "beds_available": sum(r["available"] or 0 for r in occupancy),
            "beds_out_of_service": sum(r["out_of_service"] or 0 for r in occupancy),
            "medicines_in_stock": pharmacy_repository.count_medicines_in_stock(
                conn, today.isoformat()),
            "low_stock": sum(1 for r in summary if r["usable_stock"] <= r["reorder_level"]),
            "expiring_batches": len(pharmacy_repository.expiring_batches(
                conn, today.isoformat(),
                (today + timedelta(days=config.EXPIRY_WARNING_DAYS)).isoformat())),
            "billed_month": billed,
            "collected_month": collected,
            "outstanding": billing_repository.outstanding_total(conn),
        }


def dashboard_charts(user, days: int = 14) -> dict:
    require(user, "dashboard.view")
    today = clock.today()
    start = today - timedelta(days=days - 1)
    month_from = (today.replace(day=1) - timedelta(days=150)).replace(day=1)
    with read_connection() as conn:
        return {
            "appointments": pd.DataFrame(appointment_repository.daily_status_counts(
                conn, start.isoformat(), (today + timedelta(days=7)).isoformat())),
            "flow": pd.DataFrame(admission_repository.daily_flow(
                conn, (today - timedelta(days=29)).isoformat(), today.isoformat())),
            "occupancy": pd.DataFrame(admission_repository.occupancy_by_ward(conn)),
            "stock": pd.DataFrame(pharmacy_repository.stock_by_category(conn,
                                                                        today.isoformat())),
            "billing": pd.DataFrame(billing_repository.monthly_billed_collected(
                conn, month_from.isoformat())),
        }


def recent_activity(user, limit: int = 8) -> dict:
    """Recent lists, only for the areas the user may see."""
    out = {}
    today = clock.today()
    with read_connection() as conn:
        if has_permission(user, "appointments.view"):
            doctor = (user.get("staff_id") or -1) if user["role"] == "DOCTOR" else None
            rows = appointment_repository.search(conn, today.isoformat(), today.isoformat(),
                                                 doctor_id=doctor)
            out["appointments"] = rows[:limit]
        if has_permission(user, "billing.view"):
            out["payments"] = billing_repository.payments(conn, limit=limit)
        if has_permission(user, "pharmacy.view"):
            out["low_stock"] = [r for r in pharmacy_repository.stock_summary(
                conn, today.isoformat(), active_only=True)
                if r["usable_stock"] <= r["reorder_level"]][:limit]
            out["expiring"] = pharmacy_repository.expiring_batches(
                conn, today.isoformat(),
                (today + timedelta(days=config.EXPIRY_WARNING_DAYS)).isoformat())[:limit]
    return out


# --- reports ---------------------------------------------------------------
# Each report: (title, permission, function(conn, date_from, date_to) -> rows)

def _patients(conn, f, t):
    return report_repository.patients_registered(conn, f, t)


def _appointments(conn, f, t):
    return appointment_repository.search(conn, f, t)


def _appointments_status(conn, f, t):
    return report_repository.appointments_by_status(conn, f, t)


def _attendance(conn, f, t):
    return staff_repository.attendance_between(conn, f, t)


def _attendance_summary(conn, f, t):
    return report_repository.attendance_summary(conn, f, t)


def _admissions(conn, f, t):
    return admission_repository.search(conn, date_from=f, date_to=t)


def _occupancy(conn, f, t):
    return admission_repository.bed_board(conn)


def _low_stock(conn, f, t):
    today = clock.ds()
    return [r for r in pharmacy_repository.stock_summary(conn, today, active_only=True)
            if r["usable_stock"] <= r["reorder_level"]]


def _expiry(conn, f, t):
    today = clock.ds()
    return (pharmacy_repository.expired_batches(conn, today)
            + pharmacy_repository.expiring_batches(conn, max(f, today), t))


def _movements(conn, f, t):
    return pharmacy_repository.movements(conn, f, t)


def _purchases(conn, f, t):
    return pharmacy_repository.purchases(conn, date_from=f, date_to=t)


def _bills(conn, f, t):
    return billing_repository.search(conn, f, t)


def _payments(conn, f, t):
    return billing_repository.payments(conn, f, t, limit=100000)


def _monthly(conn, f, t):
    return report_repository.monthly_summary(conn, f[:7] + "-01")


REPORTS = {
    "patients": ("Patients registered", "patients.view", _patients),
    "appointments": ("Appointments", "appointments.view", _appointments),
    "appointments_status": ("Appointments by status", "appointments.view", _appointments_status),
    "attendance": ("Staff attendance", "staff.view", _attendance),
    "attendance_summary": ("Attendance summary", "staff.view", _attendance_summary),
    "admissions": ("Admissions", "admissions.view", _admissions),
    "occupancy": ("Current bed occupancy", "admissions.view", _occupancy),
    "low_stock": ("Low-stock medicines", "pharmacy.view", _low_stock),
    "expiry": ("Near-expiry and expired batches", "pharmacy.view", _expiry),
    "movements": ("Stock movement history", "pharmacy.view", _movements),
    "purchases": ("Purchase receipts", "suppliers.view", _purchases),
    "bills": ("Bills and balances", "billing.view", _bills),
    "payments": ("Payments", "billing.view", _payments),
    "monthly": ("Monthly summary", "billing.view", _monthly),
}


def available_reports(user) -> dict:
    require(user, "reports.view")
    return {k: r[0] for k, r in REPORTS.items() if has_permission(user, r[1])}


def run_report(user, key: str, date_from: date, date_to: date) -> pd.DataFrame:
    require(user, "reports.view")
    title, permission, fn = REPORTS[key]
    require(user, permission)
    with read_connection() as conn:
        rows = fn(conn, date_from.isoformat(), date_to.isoformat())
    df = pd.DataFrame(rows)
    # Present money columns in rupees for readers and exports.
    for col in [c for c in df.columns if c.endswith("_minor")]:
        df[col.removesuffix("_minor")] = df.pop(col) / 100
    return df
