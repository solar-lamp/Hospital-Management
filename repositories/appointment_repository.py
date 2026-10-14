from repositories.common import many, one, scalar
from utils import clock

# Statuses that occupy a doctor's time slot. Cancelled and no-show do not.
BLOCKING_STATUSES = ("SCHEDULED", "CONFIRMED", "COMPLETED")

BASE_SELECT = (
    "SELECT a.appointment_id, a.start_at, a.end_at, a.status, a.reason,"
    " a.patient_id, p.patient_code, p.full_name AS patient_name,"
    " a.doctor_id, s.full_name AS doctor_name, d.name AS department"
    " FROM appointments a"
    " JOIN patients p ON p.patient_id = a.patient_id"
    " JOIN staff s ON s.staff_id = a.doctor_id"
    " LEFT JOIN departments d ON d.department_id = s.department_id"
)


def insert(conn, patient_id, doctor_id, start_at, end_at, reason, user_id):
    return conn.execute(
        "INSERT INTO appointments (patient_id, doctor_id, start_at, end_at, reason,"
        " created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (patient_id, doctor_id, start_at, end_at, reason, user_id, clock.ts()),
    ).lastrowid


def find_overlaps(conn, doctor_id, start_at, end_at, exclude_id=None):
    """Active appointments whose interval intersects [start_at, end_at)."""
    sql = (BASE_SELECT + " WHERE a.doctor_id = ? AND a.start_at < ? AND a.end_at > ?"
           f" AND a.status IN ({', '.join('?' for _ in BLOCKING_STATUSES)})")
    params = [doctor_id, end_at, start_at, *BLOCKING_STATUSES]
    if exclude_id:
        sql += " AND a.appointment_id != ?"
        params.append(exclude_id)
    return many(conn, sql, params)


def get(conn, appointment_id):
    return one(conn, BASE_SELECT + " WHERE a.appointment_id = ?", (appointment_id,))


def set_status(conn, appointment_id, status):
    conn.execute("UPDATE appointments SET status = ? WHERE appointment_id = ?",
                 (status, appointment_id))


def reschedule(conn, appointment_id, start_at, end_at):
    conn.execute("UPDATE appointments SET start_at = ?, end_at = ? WHERE appointment_id = ?",
                 (start_at, end_at, appointment_id))


def search(conn, date_from=None, date_to=None, doctor_id=None, patient_id=None, status=None,
           limit=1000):
    sql = BASE_SELECT + " WHERE 1 = 1"
    params: list = []
    if date_from:
        sql += " AND a.start_at >= ?"
        params.append(f"{date_from} 00:00:00")
    if date_to:
        sql += " AND a.start_at <= ?"
        params.append(f"{date_to} 23:59:59")
    if doctor_id:
        sql += " AND a.doctor_id = ?"
        params.append(doctor_id)
    if patient_id:
        sql += " AND a.patient_id = ?"
        params.append(patient_id)
    if status:
        sql += " AND a.status = ?"
        params.append(status)
    sql += " ORDER BY a.start_at LIMIT ?"
    params.append(limit)
    return many(conn, sql, params)


def count_on(conn, day, statuses=BLOCKING_STATUSES):
    return scalar(conn, "SELECT COUNT(*) FROM appointments WHERE start_at BETWEEN ? AND ?"
                        f" AND status IN ({', '.join('?' for _ in statuses)})",
                  (f"{day} 00:00:00", f"{day} 23:59:59", *statuses))


def daily_status_counts(conn, date_from, date_to):
    return many(conn, "SELECT substr(start_at, 1, 10) AS day, status, COUNT(*) AS appointments"
                      " FROM appointments WHERE start_at BETWEEN ? AND ?"
                      " GROUP BY day, status ORDER BY day",
                (f"{date_from} 00:00:00", f"{date_to} 23:59:59"))
