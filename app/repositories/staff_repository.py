import uuid

from repositories.common import like, many, one, scalar
from utils import clock

FIELDS = ("full_name", "role", "department_id", "specialization", "phone", "email",
          "joining_date", "status")


# --- departments -----------------------------------------------------------

def list_departments(conn):
    return many(conn, "SELECT d.department_id, d.name, d.description,"
                      " (SELECT COUNT(*) FROM staff s WHERE s.department_id = d.department_id"
                      "  AND s.status = 'ACTIVE') AS active_staff"
                      " FROM departments d ORDER BY d.name")


def get_department(conn, department_id):
    return one(conn, "SELECT * FROM departments WHERE department_id = ?", (department_id,))


def insert_department(conn, name, description):
    return conn.execute("INSERT INTO departments (name, description) VALUES (?, ?)",
                        (name, description)).lastrowid


def update_department(conn, department_id, name, description):
    conn.execute("UPDATE departments SET name = ?, description = ? WHERE department_id = ?",
                 (name, description, department_id))


# --- staff -----------------------------------------------------------------

def insert(conn, data: dict) -> int:
    cur = conn.execute(
        f"INSERT INTO staff (staff_code, {', '.join(FIELDS)}, created_at)"
        f" VALUES (?, {', '.join('?' for _ in FIELDS)}, ?)",
        (f"TMP-{uuid.uuid4().hex}", *[data.get(f) for f in FIELDS], clock.ts()),
    )
    staff_id = cur.lastrowid
    conn.execute("UPDATE staff SET staff_code = ? WHERE staff_id = ?",
                 (f"STF-{staff_id:04d}", staff_id))
    return staff_id


def update(conn, staff_id, data: dict):
    conn.execute(f"UPDATE staff SET {', '.join(f'{f} = ?' for f in FIELDS)} WHERE staff_id = ?",
                 (*[data.get(f) for f in FIELDS], staff_id))


def get(conn, staff_id):
    return one(conn, "SELECT s.*, d.name AS department FROM staff s"
                     " LEFT JOIN departments d ON d.department_id = s.department_id"
                     " WHERE s.staff_id = ?", (staff_id,))


def search(conn, term=None, role=None, department_id=None, status=None):
    sql = ("SELECT s.staff_id, s.staff_code, s.full_name, s.role, d.name AS department,"
           " s.specialization, s.phone, s.email, s.joining_date, s.status"
           " FROM staff s LEFT JOIN departments d ON d.department_id = s.department_id"
           " WHERE 1 = 1")
    params: list = []
    if term:
        sql += " AND (s.full_name LIKE ? ESCAPE '\\' OR s.staff_code LIKE ? ESCAPE '\\')"
        params += [like(term)] * 2
    if role:
        sql += " AND s.role = ?"
        params.append(role)
    if department_id:
        sql += " AND s.department_id = ?"
        params.append(department_id)
    if status:
        sql += " AND s.status = ?"
        params.append(status)
    return many(conn, sql + " ORDER BY s.full_name", params)


def options(conn, role=None, active_only=True):
    sql = ("SELECT s.staff_id, s.staff_code, s.full_name, s.role, s.specialization,"
           " d.name AS department FROM staff s"
           " LEFT JOIN departments d ON d.department_id = s.department_id WHERE 1 = 1")
    params: list = []
    if role:
        sql += " AND s.role = ?"
        params.append(role)
    if active_only:
        sql += " AND s.status = 'ACTIVE'"
    return many(conn, sql + " ORDER BY s.full_name", params)


def count_active(conn):
    return scalar(conn, "SELECT COUNT(*) FROM staff WHERE status = 'ACTIVE'")


# --- attendance ------------------------------------------------------------

def upsert_attendance(conn, staff_id, attendance_date, status, check_in, check_out, notes):
    conn.execute(
        "INSERT INTO attendance (staff_id, attendance_date, status, check_in, check_out, notes)"
        " VALUES (?, ?, ?, ?, ?, ?)"
        " ON CONFLICT (staff_id, attendance_date) DO UPDATE SET status = excluded.status,"
        " check_in = excluded.check_in, check_out = excluded.check_out, notes = excluded.notes",
        (staff_id, attendance_date, status, check_in, check_out, notes),
    )


def attendance_for_date(conn, attendance_date):
    return many(conn, "SELECT s.staff_id, s.staff_code, s.full_name, s.role, d.name AS department,"
                      " a.status, a.check_in, a.check_out, a.notes FROM staff s"
                      " LEFT JOIN departments d ON d.department_id = s.department_id"
                      " LEFT JOIN attendance a ON a.staff_id = s.staff_id AND a.attendance_date = ?"
                      " WHERE s.status = 'ACTIVE' ORDER BY s.full_name", (attendance_date,))


def attendance_between(conn, date_from, date_to, staff_id=None):
    sql = ("SELECT a.attendance_date, s.staff_code, s.full_name, s.role, d.name AS department,"
           " a.status, a.check_in, a.check_out, a.notes FROM attendance a"
           " JOIN staff s ON s.staff_id = a.staff_id"
           " LEFT JOIN departments d ON d.department_id = s.department_id"
           " WHERE a.attendance_date BETWEEN ? AND ?")
    params: list = [date_from, date_to]
    if staff_id:
        sql += " AND a.staff_id = ?"
        params.append(staff_id)
    return many(conn, sql + " ORDER BY a.attendance_date DESC, s.full_name", params)
