from repositories.common import many, one, scalar

ADMISSION_SELECT = (
    "SELECT ad.admission_id, ad.admitted_at, ad.discharged_at, ad.status, ad.reason,"
    " ad.discharge_notes, ad.patient_id, p.patient_code, p.full_name AS patient_name,"
    " ad.bed_id, b.bed_code, w.name AS ward, b.daily_rate_minor,"
    " ad.attending_doctor_id, s.full_name AS doctor_name"
    " FROM admissions ad"
    " JOIN patients p ON p.patient_id = ad.patient_id"
    " JOIN beds b ON b.bed_id = ad.bed_id"
    " JOIN wards w ON w.ward_id = b.ward_id"
    " LEFT JOIN staff s ON s.staff_id = ad.attending_doctor_id"
)


# --- wards & beds ----------------------------------------------------------

def list_wards(conn):
    return many(conn, "SELECT * FROM wards ORDER BY name")


def get_ward(conn, ward_id):
    return one(conn, "SELECT * FROM wards WHERE ward_id = ?", (ward_id,))


def insert_ward(conn, name, ward_type, floor):
    return conn.execute("INSERT INTO wards (name, ward_type, floor) VALUES (?, ?, ?)",
                        (name, ward_type, floor)).lastrowid


def insert_bed(conn, ward_id, bed_code, daily_rate_minor):
    return conn.execute("INSERT INTO beds (ward_id, bed_code, daily_rate_minor) VALUES (?, ?, ?)",
                        (ward_id, bed_code, daily_rate_minor)).lastrowid


def get_bed(conn, bed_id):
    return one(conn, "SELECT b.*, w.name AS ward FROM beds b JOIN wards w ON w.ward_id = b.ward_id"
                     " WHERE b.bed_id = ?", (bed_id,))


def set_bed_status(conn, bed_id, status):
    conn.execute("UPDATE beds SET operational_status = ? WHERE bed_id = ?", (status, bed_id))


def set_bed_rate(conn, bed_id, daily_rate_minor):
    conn.execute("UPDATE beds SET daily_rate_minor = ? WHERE bed_id = ?",
                 (daily_rate_minor, bed_id))


def bed_board(conn, ward_id=None):
    """Every bed with its derived occupancy state."""
    sql = ("SELECT b.bed_id, b.bed_code, w.ward_id, w.name AS ward, w.ward_type,"
           " b.operational_status, b.daily_rate_minor, ad.admission_id,"
           " p.patient_code, p.full_name AS patient_name, ad.admitted_at,"
           " CASE WHEN ad.admission_id IS NOT NULL THEN 'OCCUPIED'"
           "      WHEN b.operational_status = 'AVAILABLE' THEN 'AVAILABLE'"
           "      ELSE b.operational_status END AS occupancy"
           " FROM beds b JOIN wards w ON w.ward_id = b.ward_id"
           " LEFT JOIN admissions ad ON ad.bed_id = b.bed_id AND ad.status = 'ADMITTED'"
           " LEFT JOIN patients p ON p.patient_id = ad.patient_id")
    params: list = []
    if ward_id:
        sql += " WHERE w.ward_id = ?"
        params.append(ward_id)
    return many(conn, sql + " ORDER BY w.name, b.bed_code", params)


def available_beds(conn):
    return many(conn, "SELECT b.bed_id, b.bed_code, w.name AS ward, b.daily_rate_minor"
                      " FROM beds b JOIN wards w ON w.ward_id = b.ward_id"
                      " WHERE b.operational_status = 'AVAILABLE' AND NOT EXISTS ("
                      "  SELECT 1 FROM admissions ad WHERE ad.bed_id = b.bed_id"
                      "  AND ad.status = 'ADMITTED') ORDER BY w.name, b.bed_code")


def occupancy_by_ward(conn):
    return many(conn, "SELECT w.name AS ward,"
                      " SUM(CASE WHEN ad.admission_id IS NOT NULL THEN 1 ELSE 0 END) AS occupied,"
                      " SUM(CASE WHEN ad.admission_id IS NULL AND b.operational_status = 'AVAILABLE'"
                      "     THEN 1 ELSE 0 END) AS available,"
                      " SUM(CASE WHEN ad.admission_id IS NULL AND b.operational_status != 'AVAILABLE'"
                      "     THEN 1 ELSE 0 END) AS out_of_service"
                      " FROM beds b JOIN wards w ON w.ward_id = b.ward_id"
                      " LEFT JOIN admissions ad ON ad.bed_id = b.bed_id AND ad.status = 'ADMITTED'"
                      " GROUP BY w.ward_id ORDER BY w.name")


def bed_has_active_admission(conn, bed_id):
    return scalar(conn, "SELECT COUNT(*) FROM admissions WHERE bed_id = ? AND status = 'ADMITTED'",
                  (bed_id,)) > 0


# --- admissions ------------------------------------------------------------

def insert_admission(conn, patient_id, bed_id, doctor_id, admitted_at, reason, user_id):
    return conn.execute(
        "INSERT INTO admissions (patient_id, bed_id, attending_doctor_id, admitted_at, reason,"
        " created_by) VALUES (?, ?, ?, ?, ?, ?)",
        (patient_id, bed_id, doctor_id, admitted_at, reason, user_id),
    ).lastrowid


def get_admission(conn, admission_id):
    return one(conn, ADMISSION_SELECT + " WHERE ad.admission_id = ?", (admission_id,))


def active_for_patient(conn, patient_id):
    return one(conn, ADMISSION_SELECT + " WHERE ad.patient_id = ? AND ad.status = 'ADMITTED'",
               (patient_id,))


def discharge(conn, admission_id, discharged_at, notes):
    return conn.execute(
        "UPDATE admissions SET status = 'DISCHARGED', discharged_at = ?, discharge_notes = ?"
        " WHERE admission_id = ? AND status = 'ADMITTED'",
        (discharged_at, notes, admission_id),
    ).rowcount


def cancel(conn, admission_id, notes):
    return conn.execute(
        "UPDATE admissions SET status = 'CANCELLED', discharge_notes = ?"
        " WHERE admission_id = ? AND status = 'ADMITTED'",
        (notes, admission_id),
    ).rowcount


def search(conn, status=None, patient_id=None, date_from=None, date_to=None):
    sql = ADMISSION_SELECT + " WHERE 1 = 1"
    params: list = []
    if status:
        sql += " AND ad.status = ?"
        params.append(status)
    if patient_id:
        sql += " AND ad.patient_id = ?"
        params.append(patient_id)
    if date_from:
        sql += " AND ad.admitted_at >= ?"
        params.append(f"{date_from} 00:00:00")
    if date_to:
        sql += " AND ad.admitted_at <= ?"
        params.append(f"{date_to} 23:59:59")
    return many(conn, sql + " ORDER BY ad.admitted_at DESC", params)


def count_active(conn):
    return scalar(conn, "SELECT COUNT(*) FROM admissions WHERE status = 'ADMITTED'")


def daily_flow(conn, date_from, date_to):
    return many(conn,
                "SELECT day, SUM(admitted) AS admissions, SUM(discharged) AS discharges FROM ("
                " SELECT substr(admitted_at, 1, 10) AS day, 1 AS admitted, 0 AS discharged"
                " FROM admissions WHERE status != 'CANCELLED' AND admitted_at BETWEEN ? AND ?"
                " UNION ALL"
                " SELECT substr(discharged_at, 1, 10), 0, 1 FROM admissions"
                " WHERE status = 'DISCHARGED' AND discharged_at BETWEEN ? AND ?"
                ") GROUP BY day ORDER BY day",
                (f"{date_from} 00:00:00", f"{date_to} 23:59:59",
                 f"{date_from} 00:00:00", f"{date_to} 23:59:59"))
