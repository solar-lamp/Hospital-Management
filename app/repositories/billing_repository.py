import uuid

from repositories.common import many, one, scalar
from utils import clock

PAID_SUBQUERY = ("COALESCE((SELECT SUM(amount_minor) FROM payments py"
                 " WHERE py.bill_id = b.bill_id AND py.status = 'ACCEPTED'), 0)")

BILL_SELECT = (
    "SELECT b.bill_id, b.bill_number, b.bill_date, b.patient_id, p.patient_code,"
    " p.full_name AS patient_name, b.admission_id, b.appointment_id, b.subtotal_minor,"
    " b.discount_minor, b.tax_minor, b.total_minor, b.status, b.void_reason, b.notes,"
    f" {PAID_SUBQUERY} AS paid_minor,"
    f" CASE WHEN b.status = 'VOID' THEN 0 ELSE b.total_minor - {PAID_SUBQUERY} END"
    "   AS balance_minor"
    " FROM bills b JOIN patients p ON p.patient_id = b.patient_id"
)


def insert_bill(conn, patient_id, admission_id, appointment_id, bill_date, subtotal, discount,
                tax, total, notes, user_id):
    cur = conn.execute(
        "INSERT INTO bills (bill_number, patient_id, admission_id, appointment_id, bill_date,"
        " subtotal_minor, discount_minor, tax_minor, total_minor, notes, created_by, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (f"TMP-{uuid.uuid4().hex}", patient_id, admission_id, appointment_id, bill_date,
         subtotal, discount, tax, total, notes, user_id, clock.ts()),
    )
    bill_id = cur.lastrowid
    conn.execute("UPDATE bills SET bill_number = ? WHERE bill_id = ?",
                 (f"BILL-{bill_date[:4]}-{bill_id:06d}", bill_id))
    return bill_id


def insert_item(conn, bill_id, description, quantity, unit_price_minor):
    conn.execute(
        "INSERT INTO bill_items (bill_id, description, quantity, unit_price_minor,"
        " line_total_minor) VALUES (?, ?, ?, ?, ?)",
        (bill_id, description, quantity, unit_price_minor, quantity * unit_price_minor),
    )


def get_bill(conn, bill_id):
    return one(conn, BILL_SELECT + " WHERE b.bill_id = ?", (bill_id,))


def items(conn, bill_id):
    return many(conn, "SELECT * FROM bill_items WHERE bill_id = ? ORDER BY bill_item_id",
                (bill_id,))


def void_bill(conn, bill_id, reason):
    return conn.execute("UPDATE bills SET status = 'VOID', void_reason = ?"
                        " WHERE bill_id = ? AND status = 'FINAL'", (reason, bill_id)).rowcount


def search(conn, date_from=None, date_to=None, patient_id=None, status=None,
           outstanding_only=False):
    sql = BILL_SELECT + " WHERE 1 = 1"
    params: list = []
    if date_from:
        sql += " AND b.bill_date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND b.bill_date <= ?"
        params.append(date_to)
    if patient_id:
        sql += " AND b.patient_id = ?"
        params.append(patient_id)
    if status:
        sql += " AND b.status = ?"
        params.append(status)
    if outstanding_only:
        sql += f" AND b.status = 'FINAL' AND b.total_minor > {PAID_SUBQUERY}"
    return many(conn, sql + " ORDER BY b.bill_id DESC", params)


def insert_payment(conn, bill_id, amount_minor, paid_at, method, reference, user_id):
    return conn.execute(
        "INSERT INTO payments (bill_id, amount_minor, paid_at, method, reference, recorded_by,"
        " created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (bill_id, amount_minor, paid_at, method, reference, user_id, clock.ts()),
    ).lastrowid


def get_payment(conn, payment_id):
    return one(conn, "SELECT * FROM payments WHERE payment_id = ?", (payment_id,))


def void_payment(conn, payment_id, reason):
    return conn.execute("UPDATE payments SET status = 'VOID', void_reason = ?"
                        " WHERE payment_id = ? AND status = 'ACCEPTED'",
                        (reason, payment_id)).rowcount


def payments_for_bill(conn, bill_id):
    return many(conn, "SELECT py.*, u.username AS recorded_by_user FROM payments py"
                      " LEFT JOIN users u ON u.user_id = py.recorded_by"
                      " WHERE py.bill_id = ? ORDER BY py.payment_id", (bill_id,))


def payments(conn, date_from=None, date_to=None, limit=1000):
    sql = ("SELECT py.payment_id, py.paid_at, b.bill_number, p.full_name AS patient_name,"
           " py.amount_minor, py.method, py.reference, py.status, u.username AS recorded_by"
           " FROM payments py JOIN bills b ON b.bill_id = py.bill_id"
           " JOIN patients p ON p.patient_id = b.patient_id"
           " LEFT JOIN users u ON u.user_id = py.recorded_by WHERE 1 = 1")
    params: list = []
    if date_from:
        sql += " AND py.paid_at >= ?"
        params.append(f"{date_from} 00:00:00")
    if date_to:
        sql += " AND py.paid_at <= ?"
        params.append(f"{date_to} 23:59:59")
    sql += " ORDER BY py.payment_id DESC LIMIT ?"
    params.append(limit)
    return many(conn, sql, params)


def totals(conn, date_from=None, date_to=None):
    """Billed (valid bills in period) and collected (accepted payments in period)."""
    billed = scalar(conn, "SELECT COALESCE(SUM(total_minor), 0) FROM bills"
                          " WHERE status = 'FINAL' AND bill_date BETWEEN ? AND ?",
                    (date_from or "0000-01-01", date_to or "9999-12-31"))
    collected = scalar(conn, "SELECT COALESCE(SUM(amount_minor), 0) FROM payments"
                             " WHERE status = 'ACCEPTED' AND paid_at BETWEEN ? AND ?",
                       (f"{date_from or '0000-01-01'} 00:00:00",
                        f"{date_to or '9999-12-31'} 23:59:59"))
    return billed, collected


def outstanding_total(conn):
    return scalar(conn, f"SELECT COALESCE(SUM(b.total_minor - {PAID_SUBQUERY}), 0)"
                        " FROM bills b WHERE b.status = 'FINAL'")


def monthly_billed_collected(conn, month_from):
    return many(conn,
                "SELECT month, SUM(billed) AS billed_minor, SUM(collected) AS collected_minor"
                " FROM (SELECT substr(bill_date, 1, 7) AS month, total_minor AS billed,"
                "  0 AS collected FROM bills WHERE status = 'FINAL' AND bill_date >= ?"
                " UNION ALL SELECT substr(paid_at, 1, 7), 0, amount_minor FROM payments"
                "  WHERE status = 'ACCEPTED' AND paid_at >= ?)"
                " GROUP BY month ORDER BY month", (month_from, f"{month_from} 00:00:00"))
