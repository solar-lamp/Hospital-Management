import uuid

from repositories.common import like, many, one, scalar
from utils import clock

FIELDS = ("full_name", "date_of_birth", "gender", "blood_group", "phone", "email",
          "address", "emergency_contact")


def insert(conn, data: dict) -> int:
    cur = conn.execute(
        f"INSERT INTO patients (patient_code, {', '.join(FIELDS)}, created_at)"
        f" VALUES (?, {', '.join('?' for _ in FIELDS)}, ?)",
        (f"TMP-{uuid.uuid4().hex}", *[data.get(f) for f in FIELDS], clock.ts()),
    )
    patient_id = cur.lastrowid
    conn.execute("UPDATE patients SET patient_code = ? WHERE patient_id = ?",
                 (f"PAT-{patient_id:06d}", patient_id))
    return patient_id


def update(conn, patient_id: int, data: dict):
    conn.execute(
        f"UPDATE patients SET {', '.join(f'{f} = ?' for f in FIELDS)} WHERE patient_id = ?",
        (*[data.get(f) for f in FIELDS], patient_id),
    )


def set_status(conn, patient_id, status):
    conn.execute("UPDATE patients SET status = ? WHERE patient_id = ?", (status, patient_id))


def get(conn, patient_id):
    return one(conn, "SELECT * FROM patients WHERE patient_id = ?", (patient_id,))


def find_duplicates(conn, full_name, date_of_birth, phone, exclude_id=None):
    sql = ("SELECT patient_code, full_name, date_of_birth, phone FROM patients"
           " WHERE lower(full_name) = lower(?)"
           " AND (date_of_birth = ? OR phone = ?)")
    params = [full_name, date_of_birth, phone]
    if exclude_id:
        sql += " AND patient_id != ?"
        params.append(exclude_id)
    return many(conn, sql, params)


def search(conn, term=None, status=None, registered_from=None, registered_to=None, limit=500):
    sql = "SELECT * FROM patients WHERE 1 = 1"
    params: list = []
    if term:
        sql += (" AND (patient_code LIKE ? ESCAPE '\\' OR full_name LIKE ? ESCAPE '\\'"
                " OR phone LIKE ? ESCAPE '\\')")
        params += [like(term)] * 3
    if status:
        sql += " AND status = ?"
        params.append(status)
    if registered_from:
        sql += " AND created_at >= ?"
        params.append(f"{registered_from} 00:00:00")
    if registered_to:
        sql += " AND created_at <= ?"
        params.append(f"{registered_to} 23:59:59")
    sql += " ORDER BY patient_id DESC LIMIT ?"
    params.append(limit)
    return many(conn, sql, params)


def options(conn, active_only=True):
    sql = "SELECT patient_id, patient_code, full_name FROM patients"
    if active_only:
        sql += " WHERE status = 'ACTIVE'"
    return many(conn, sql + " ORDER BY full_name")


def count(conn, status=None):
    if status:
        return scalar(conn, "SELECT COUNT(*) FROM patients WHERE status = ?", (status,))
    return scalar(conn, "SELECT COUNT(*) FROM patients")
