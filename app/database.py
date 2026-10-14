"""SQLite connection helpers, transactions, schema migrations and backups."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

import config

# ---------------------------------------------------------------------------
# Schema. Each migration is applied once and recorded in schema_migrations.
# Never edit a released migration: append a new one instead.
# ---------------------------------------------------------------------------

MIGRATION_1 = """
CREATE TABLE departments (
    department_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description TEXT
);

CREATE TABLE staff (
    staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_code TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL CHECK (length(trim(full_name)) > 0),
    role TEXT NOT NULL CHECK (role IN (
        'DOCTOR', 'NURSE', 'PHARMACIST', 'RECEPTIONIST',
        'ADMINISTRATOR', 'BILLING', 'LAB_TECHNICIAN', 'OTHER')),
    department_id INTEGER REFERENCES departments(department_id),
    specialization TEXT,
    phone TEXT,
    email TEXT,
    joining_date TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE')),
    created_at TEXT NOT NULL
);

CREATE TABLE attendance (
    attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id INTEGER NOT NULL REFERENCES staff(staff_id),
    attendance_date TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PRESENT', 'ABSENT', 'LEAVE', 'HALF_DAY')),
    check_in TEXT,
    check_out TEXT,
    notes TEXT,
    UNIQUE (staff_id, attendance_date),
    CHECK (check_out IS NULL OR check_in IS NULL OR check_out >= check_in)
);

CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    full_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN (
        'ADMIN', 'RECEPTIONIST', 'DOCTOR', 'NURSE', 'PHARMACIST', 'BILLING')),
    staff_id INTEGER REFERENCES staff(staff_id),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL,
    last_login_at TEXT
);

CREATE TABLE patients (
    patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_code TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL CHECK (length(trim(full_name)) > 0),
    date_of_birth TEXT,
    gender TEXT CHECK (gender IS NULL OR gender IN ('MALE', 'FEMALE', 'OTHER')),
    blood_group TEXT,
    phone TEXT,
    email TEXT,
    address TEXT,
    emergency_contact TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE')),
    created_at TEXT NOT NULL
);
CREATE INDEX idx_patients_name ON patients(full_name);
CREATE INDEX idx_patients_created ON patients(created_at);

CREATE TABLE appointments (
    appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
    doctor_id INTEGER NOT NULL REFERENCES staff(staff_id),
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'SCHEDULED' CHECK (status IN (
        'SCHEDULED', 'CONFIRMED', 'COMPLETED', 'CANCELLED', 'NO_SHOW')),
    created_by INTEGER REFERENCES users(user_id),
    created_at TEXT NOT NULL,
    CHECK (end_at > start_at)
);
CREATE INDEX idx_appointments_doctor_start ON appointments(doctor_id, start_at);
CREATE INDEX idx_appointments_patient ON appointments(patient_id);

CREATE TABLE wards (
    ward_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    ward_type TEXT,
    floor TEXT
);

CREATE TABLE beds (
    bed_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ward_id INTEGER NOT NULL REFERENCES wards(ward_id),
    bed_code TEXT NOT NULL UNIQUE COLLATE NOCASE,
    operational_status TEXT NOT NULL DEFAULT 'AVAILABLE' CHECK (operational_status IN (
        'AVAILABLE', 'UNAVAILABLE', 'MAINTENANCE')),
    daily_rate_minor INTEGER NOT NULL DEFAULT 0 CHECK (daily_rate_minor >= 0)
);

CREATE TABLE admissions (
    admission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
    bed_id INTEGER NOT NULL REFERENCES beds(bed_id),
    attending_doctor_id INTEGER REFERENCES staff(staff_id),
    admitted_at TEXT NOT NULL,
    discharged_at TEXT,
    reason TEXT,
    discharge_notes TEXT,
    status TEXT NOT NULL DEFAULT 'ADMITTED' CHECK (status IN (
        'ADMITTED', 'DISCHARGED', 'CANCELLED')),
    created_by INTEGER REFERENCES users(user_id),
    CHECK (discharged_at IS NULL OR discharged_at >= admitted_at),
    CHECK ((status = 'ADMITTED') = (discharged_at IS NULL) OR status = 'CANCELLED')
);
-- A bed can hold at most one active admission, and a patient can be admitted
-- to at most one bed at a time.
CREATE UNIQUE INDEX one_active_admission_per_bed
    ON admissions(bed_id) WHERE status = 'ADMITTED';
CREATE UNIQUE INDEX one_active_admission_per_patient
    ON admissions(patient_id) WHERE status = 'ADMITTED';

CREATE TABLE suppliers (
    supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    contact_person TEXT,
    phone TEXT,
    email TEXT,
    address TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE'))
);

CREATE TABLE medicines (
    medicine_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    generic_name TEXT,
    strength TEXT,
    form TEXT,
    category TEXT,
    unit TEXT NOT NULL DEFAULT 'unit',
    reorder_level INTEGER NOT NULL DEFAULT 10 CHECK (reorder_level >= 0),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    UNIQUE (name, strength, form)
);

CREATE TABLE medicine_batches (
    batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    medicine_id INTEGER NOT NULL REFERENCES medicines(medicine_id),
    supplier_id INTEGER REFERENCES suppliers(supplier_id),
    batch_number TEXT NOT NULL,
    expiry_date TEXT NOT NULL,
    quantity_on_hand INTEGER NOT NULL DEFAULT 0 CHECK (quantity_on_hand >= 0),
    purchase_price_minor INTEGER CHECK (purchase_price_minor IS NULL OR purchase_price_minor >= 0),
    selling_price_minor INTEGER CHECK (selling_price_minor IS NULL OR selling_price_minor >= 0),
    received_at TEXT NOT NULL,
    UNIQUE (medicine_id, batch_number)
);
CREATE INDEX idx_batches_medicine_expiry ON medicine_batches(medicine_id, expiry_date);

CREATE TABLE stock_movements (
    movement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES medicine_batches(batch_id),
    movement_type TEXT NOT NULL CHECK (movement_type IN (
        'RECEIPT', 'ISSUE', 'RETURN', 'ADJUSTMENT')),
    quantity_delta INTEGER NOT NULL CHECK (quantity_delta != 0),
    reason TEXT,
    reference TEXT,
    created_by INTEGER REFERENCES users(user_id),
    created_at TEXT NOT NULL
);
CREATE INDEX idx_movements_batch ON stock_movements(batch_id);
CREATE INDEX idx_movements_created ON stock_movements(created_at);

CREATE TABLE purchases (
    purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(supplier_id),
    received_date TEXT NOT NULL,
    invoice_reference TEXT,
    created_by INTEGER REFERENCES users(user_id),
    created_at TEXT NOT NULL
);

CREATE TABLE purchase_items (
    purchase_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id INTEGER NOT NULL REFERENCES purchases(purchase_id),
    batch_id INTEGER NOT NULL REFERENCES medicine_batches(batch_id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_cost_minor INTEGER NOT NULL CHECK (unit_cost_minor >= 0)
);

CREATE TABLE bills (
    bill_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_number TEXT NOT NULL UNIQUE,
    patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
    admission_id INTEGER REFERENCES admissions(admission_id),
    appointment_id INTEGER REFERENCES appointments(appointment_id),
    bill_date TEXT NOT NULL,
    subtotal_minor INTEGER NOT NULL CHECK (subtotal_minor >= 0),
    discount_minor INTEGER NOT NULL DEFAULT 0 CHECK (discount_minor >= 0),
    tax_minor INTEGER NOT NULL DEFAULT 0 CHECK (tax_minor >= 0),
    total_minor INTEGER NOT NULL CHECK (total_minor >= 0),
    status TEXT NOT NULL DEFAULT 'FINAL' CHECK (status IN ('FINAL', 'VOID')),
    void_reason TEXT,
    notes TEXT,
    created_by INTEGER REFERENCES users(user_id),
    created_at TEXT NOT NULL,
    CHECK (discount_minor <= subtotal_minor),
    CHECK (total_minor = subtotal_minor - discount_minor + tax_minor)
);
CREATE INDEX idx_bills_patient ON bills(patient_id);
CREATE INDEX idx_bills_date ON bills(bill_date);

CREATE TABLE bill_items (
    bill_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER NOT NULL REFERENCES bills(bill_id),
    description TEXT NOT NULL CHECK (length(trim(description)) > 0),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_minor INTEGER NOT NULL CHECK (unit_price_minor >= 0),
    line_total_minor INTEGER NOT NULL CHECK (line_total_minor = quantity * unit_price_minor)
);

CREATE TABLE payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER NOT NULL REFERENCES bills(bill_id),
    amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
    paid_at TEXT NOT NULL,
    method TEXT NOT NULL CHECK (method IN ('CASH', 'CARD', 'UPI', 'INSURANCE', 'BANK_TRANSFER')),
    reference TEXT,
    status TEXT NOT NULL DEFAULT 'ACCEPTED' CHECK (status IN ('ACCEPTED', 'VOID')),
    void_reason TEXT,
    recorded_by INTEGER REFERENCES users(user_id),
    created_at TEXT NOT NULL
);
CREATE INDEX idx_payments_bill ON payments(bill_id);

CREATE TABLE audit_logs (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(user_id),
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    description TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_audit_created ON audit_logs(created_at);

-- Audit history is append-only.
CREATE TRIGGER audit_logs_no_update BEFORE UPDATE ON audit_logs
BEGIN SELECT RAISE(ABORT, 'audit log entries cannot be modified'); END;
CREATE TRIGGER audit_logs_no_delete BEFORE DELETE ON audit_logs
BEGIN SELECT RAISE(ABORT, 'audit log entries cannot be deleted'); END;
"""

MIGRATIONS: list[tuple[int, str]] = [
    (1, MIGRATION_1),
]

# Tables that must exist for a file to be accepted as a restore source.
REQUIRED_TABLES = {
    "patients", "staff", "users", "appointments", "admissions", "beds",
    "medicines", "medicine_batches", "stock_movements", "bills", "payments",
}


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a short-lived connection with foreign keys enforced.

    ``isolation_level=None`` puts sqlite3 in autocommit mode; multi-statement
    writes use :func:`transaction`, which issues an explicit BEGIN IMMEDIATE.
    """
    path = Path(db_path) if db_path else config.get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def read_connection():
    """Connection for read-only queries; always closed afterwards."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction():
    """Run a unit of work atomically.

    BEGIN IMMEDIATE takes the write lock up front so read-check-write
    sequences (stock levels, bed occupancy, appointment overlaps) cannot
    interleave with another writer. Any exception rolls everything back.
    """
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def current_schema_version(conn: sqlite3.Connection) -> int:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL"
        " DEFAULT CURRENT_TIMESTAMP)"
    )
    row = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
    return row["v"] or 0


def init_db(db_path: Path | str | None = None) -> int:
    """Create or upgrade the schema. Returns the resulting schema version."""
    conn = get_connection(db_path)
    try:
        version = current_schema_version(conn)
        for number, sql in MIGRATIONS:
            if number <= version:
                continue
            # executescript commits implicitly, so wrap the statements
            # ourselves to keep each migration atomic.
            conn.executescript(
                "BEGIN;\n" + sql
                + f"\nINSERT INTO schema_migrations (version) VALUES ({int(number)});\nCOMMIT;"
            )
            version = number
        return version
    finally:
        conn.close()


def is_empty() -> bool:
    with read_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


# ---------------------------------------------------------------------------
# Backup and restore (uses SQLite's online backup API, safe on a live DB)
# ---------------------------------------------------------------------------

def backup_to(dest: Path | str) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = get_connection()
    try:
        target = sqlite3.connect(dest)
        try:
            src.backup(target)
        finally:
            target.close()
    finally:
        src.close()
    return dest


def backup_bytes() -> bytes:
    """Serialize the live database (used for the download button)."""
    src = get_connection()
    try:
        mem = sqlite3.connect(":memory:")
        try:
            src.backup(mem)
            return mem.serialize()
        finally:
            mem.close()
    finally:
        src.close()


def validate_backup(path: Path | str) -> None:
    """Raise ValueError unless ``path`` is an intact MediTrack database."""
    try:
        conn = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)
        try:
            ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'")}
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        raise ValueError("The file is not a valid SQLite database.") from exc
    if ok != "ok":
        raise ValueError("The backup failed the SQLite integrity check.")
    missing = REQUIRED_TABLES - tables
    if missing:
        raise ValueError("The backup is missing tables: " + ", ".join(sorted(missing)))


def restore_from(path: Path | str) -> None:
    """Replace the live database contents with a validated backup."""
    validate_backup(path)
    source = sqlite3.connect(Path(path))
    try:
        target = get_connection()
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()
    init_db()  # bring an older backup up to the current schema
