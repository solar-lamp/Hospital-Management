# Hospital Management System

## Full Architecture, Development Plan, and Technical Understanding

**Technology:** Python, Streamlit, SQLite\
**Project type:** College-level hospital management and resource
tracking application\
**Purpose:** A detailed plan covering architecture, modules, database
design, workflows, security, development phases, testing, and viva
preparation.

> This document describes the proposed design. It does not claim that
> all modules have already been implemented. Use fictional data for
> demonstrations.

------------------------------------------------------------------------

# 1. Project Overview

## 1.1 Project title

**MediTrack: Hospital Management and Resource Tracking System**

The name can be changed to match college requirements.

## 1.2 Problem statement

Hospitals manage connected activities such as patient registration,
appointments, doctors and staff, admissions, bed allocation, pharmacy
stock, suppliers, billing, and reports. When information is stored in
separate registers or spreadsheets, it can be difficult to search
records, identify low-stock medicines, check bed availability, avoid
duplicate entries, and prepare reports.

This project brings these activities into one browser-based application.
Streamlit provides the user interface, Python contains the business
logic, and SQLite stores the records in a local database file.

## 1.3 Objectives

-   Register, search, view, update, and archive patients.
-   Manage doctors, nurses, pharmacists, receptionists, and other staff.
-   Maintain departments and staff attendance.
-   Schedule and track appointments.
-   Track admissions, wards, rooms, beds, and discharge.
-   Manage medicines, batches, suppliers, stock receipts, stock issues,
    and expiry alerts.
-   Prepare bills and record payments.
-   Display operational metrics and charts.
-   Generate filtered reports and exports.
-   Apply validation, database constraints, permissions, and reliable
    transactions.
-   Provide documentation and test evidence for the college submission.

## 1.4 Intended users

  -----------------------------------------------------------------------
  Role                                Responsibilities
  ----------------------------------- -----------------------------------
  Administrator                       Manage users, staff, departments,
                                      settings, and overall reports

  Receptionist                        Register patients, search records,
                                      schedule appointments, coordinate
                                      admissions

  Doctor                              View assigned appointments and
                                      permitted patient information

  Nurse                               View assigned patients and
                                      permitted ward information

  Pharmacist                          Manage medicine batches, stock
                                      receipts, issues, and expiry alerts

  Billing staff                       Create bills, record payments, and
                                      view billing reports
  -----------------------------------------------------------------------

Start with Admin, Receptionist, Pharmacist, and Billing roles. Add
Doctor and Nurse access after the main workflows work. Hiding a menu
item is not sufficient security: protected operations must check
permissions in the Python service layer too.

## 1.5 Scope and limitations

This is an educational prototype, not a clinically certified hospital
information system. Use synthetic/demo data. Do not store real patient
information unless security, privacy, access control, backup,
deployment, and applicable legal requirements have been reviewed. Do not
use the application as the sole system for clinical decisions,
prescriptions, emergency triage, or regulated medical records.

SQLite is appropriate for a local prototype or small single-instance
application. A large multi-user deployment or multiple application
instances may require a server database such as PostgreSQL and a
production-grade architecture review.

------------------------------------------------------------------------

# 2. Technology Stack

  -----------------------------------------------------------------------
  Technology                          Purpose
  ----------------------------------- -----------------------------------
  Python                              Application logic, validation,
                                      calculations, and reports

  Streamlit                           Web interface, navigation, forms,
                                      tables, metrics, charts

  SQLite                              Relational database stored in a
                                      local `.db` file

  `sqlite3`                           Python's built-in SQLite database
                                      driver

  pandas                              Tabular data processing and report
                                      exports

  Plotly                              Interactive charts

  `openpyxl`                          Optional Excel `.xlsx` export

  Argon2 or bcrypt library            Modern password hashing

  `pytest`                            Automated tests

  Git/GitHub                          Version control and source sharing
  -----------------------------------------------------------------------

SQLite is included with standard Python installations, so it generally
does not need to be installed separately.

## 2.1 How the system runs

1.  The user opens the Streamlit app in a browser.
2.  The user selects a page or module.
3.  Streamlit executes the corresponding Python code.
4.  The page calls service functions.
5.  Service functions validate the request and enforce business rules.
6.  Repository/database functions execute parameterized SQL.
7.  SQLite returns rows or persists changes.
8.  Python formats the result and Streamlit displays the updated page.

**Streamlit reruns the Python script after many user interactions.** Do
not assume normal Python variables persist between reruns. Use
`st.session_state` for temporary UI state and SQLite for persistent
application data.

------------------------------------------------------------------------

# 3. High-Level Architecture

``` text
+-------------------------------------------------------+
|                    User's Browser                     |
|        Dashboard, Forms, Tables, Charts, Alerts        |
+---------------------------+---------------------------+
                            |
                            v
+-------------------------------------------------------+
|                   Streamlit UI Layer                  |
| app.py and pages: Patients, Staff, Pharmacy, etc.     |
| Navigation, forms, filters, display logic             |
+---------------------------+---------------------------+
                            |
                            v
+-------------------------------------------------------+
|                Service / Business Layer               |
| PatientService, StaffService, PharmacyService,         |
| AppointmentService, AdmissionService, BillingService  |
| Validation, permissions, business rules, transactions  |
+---------------------------+---------------------------+
                            |
                            v
+-------------------------------------------------------+
|                   Data Access Layer                   |
| Connection helpers, repository functions, SQL queries |
| Parameterized SQL, transaction handling, row mapping  |
+---------------------------+---------------------------+
                            |
                            v
+-------------------------------------------------------+
|                       SQLite                          |
| patients, staff, appointments, beds, medicines,        |
| medicine_batches, stock_movements, bills, payments,    |
| users, audit_logs, and related tables                 |
+-------------------------------------------------------+
```

## 3.1 Responsibilities by layer

### UI layer

-   Collect user input and display results.
-   Provide navigation, filters, forms, tables, and charts.
-   Show validation errors and success messages.
-   Avoid long SQL statements and duplicated business rules.

### Service layer

-   Validate that an operation is allowed.
-   Enforce workflow rules, such as not assigning an occupied bed.
-   Check the user's permission.
-   Group related changes into a transaction when needed.

### Data access layer

-   Open and close database connections.
-   Execute parameterized SQL.
-   Read and write rows.
-   Commit successful transactions and roll back failures.

### Database layer

-   Enforce primary keys, foreign keys, uniqueness, and check
    constraints.
-   Preserve relationships between records.
-   Store data after the application closes.

------------------------------------------------------------------------

# 4. Recommended Folder Structure

``` text
hospital_management/
|
|-- app.py
|-- database.py
|-- config.py
|-- requirements.txt
|-- README.md
|-- .gitignore
|-- .env.example
|
|-- assets/
|   |-- logo.png
|   |-- styles.css
|
|-- pages/
|   |-- 1_Patients.py
|   |-- 2_Doctors_and_Staff.py
|   |-- 3_Appointments.py
|   |-- 4_Admissions_and_Beds.py
|   |-- 5_Medicine_Inventory.py
|   |-- 6_Suppliers.py
|   |-- 7_Billing_and_Payments.py
|   |-- 8_Reports.py
|   |-- 9_User_Management.py
|
|-- services/
|   |-- auth_service.py
|   |-- patient_service.py
|   |-- staff_service.py
|   |-- appointment_service.py
|   |-- admission_service.py
|   |-- pharmacy_service.py
|   |-- billing_service.py
|   |-- report_service.py
|
|-- repositories/
|   |-- patient_repository.py
|   |-- staff_repository.py
|   |-- appointment_repository.py
|   |-- admission_repository.py
|   |-- pharmacy_repository.py
|   |-- billing_repository.py
|   |-- user_repository.py
|
|-- utils/
|   |-- validators.py
|   |-- formatting.py
|   |-- export_utils.py
|   |-- permissions.py
|
|-- tests/
|   |-- test_patients.py
|   |-- test_pharmacy.py
|   |-- test_beds.py
|   |-- test_billing.py
|
|-- data/
    |-- hospital.db
    |-- backups/
```

### File responsibilities

-   `app.py`: page configuration, authentication gate, main dashboard,
    global navigation.
-   `database.py`: connection helper, schema initialization, migrations,
    database setup.
-   `config.py`: non-secret configuration such as database path and
    display settings.
-   `pages/`: user-facing Streamlit screens.
-   `services/`: business rules and workflow operations.
-   `repositories/`: SQL queries and data access functions.
-   `utils/validators.py`: reusable validation for names, dates,
    quantities, and amounts.
-   `utils/permissions.py`: centralized role and permission checks.
-   `utils/export_utils.py`: safe CSV/Excel exports.
-   `tests/`: automated checks for core workflows.
-   `data/hospital.db`: local database created by the application. Never
    commit a database containing private or real patient information.
-   `data/backups/`: protected backup copies.

For a small project, service and repository code can initially be
combined. Split it as the code grows. Avoid making every page implement
its own database rules.

------------------------------------------------------------------------

# 5. Functional Modules

## 5.1 Dashboard

### Metrics

-   Total registered patients.
-   Active staff count.
-   Appointments scheduled for today.
-   Patients currently admitted.
-   Available and occupied beds.
-   Medicine types/batches currently in stock.
-   Low-stock medicine alerts.
-   Near-expiry batch alerts.
-   Outstanding bills and payments received.

### Charts

-   Appointments by day or status.
-   Admissions and discharges over time.
-   Bed occupancy by ward.
-   Medicine stock by category.
-   Monthly billed amount compared with payments collected.

### Rules

-   Every metric must come from database queries, not hard-coded demo
    numbers.
-   Define each metric precisely.
-   Handle empty databases without errors.
-   Use date ranges and filters where useful.
-   Avoid exposing unnecessary patient details on shared screens.

## 5.2 Patient management

### Functions

-   Register a patient and generate a unique patient code.
-   Search by patient code or name.
-   Filter by registration date.
-   View and update permitted details.
-   View appointment, admission, and billing history.
-   Archive or deactivate a record according to policy.

### Suggested fields

-   `patient_id`: internal primary key.
-   `patient_code`: human-readable unique identifier.
-   `full_name`.
-   `date_of_birth` or age derived from date of birth.
-   `gender`, if required.
-   `phone`, `email`, and `address`, as appropriate.
-   `emergency_contact`, optional and protected.
-   `created_at`.
-   `status`.

### Validation

-   Name cannot be blank.
-   Date of birth cannot be in the future.
-   Phone number must follow a documented format rule.
-   Patient code must be unique.
-   Optional fields should remain optional when not needed.

Avoid permanently deleting a patient who has appointments, admissions,
or bills. Prefer an archival/status approach and retain only records
required by the project's policy.

## 5.3 Doctors and staff

### Functions

-   Add and update staff.
-   Assign department and job role.
-   Search by name, role, and department.
-   Record employment status.
-   Track attendance and shifts.
-   Add leave tracking if time permits.

### Suggested fields

-   Staff ID and unique staff code.
-   Full name.
-   Role: doctor, nurse, pharmacist, receptionist, administrator, etc.
-   Department.
-   Phone/email if required.
-   Joining date.
-   Employment status.

### Attendance

-   Staff member.
-   Attendance date.
-   Check-in/check-out, if used.
-   Status: present, absent, leave, or half-day.
-   Notes if necessary.

Use a unique constraint on `(staff_id, attendance_date)` if only one
record per day is permitted. If shifts or multiple clock events are
required, use a separate attendance-event design.

## 5.4 Departments

Examples: General Medicine, Pediatrics, Orthopedics, Cardiology,
Pharmacy, Laboratory, and Administration.

Store departments in a separate table instead of repeating free-text
names in each staff row. This improves consistency and filtering.

## 5.5 Appointments

### Functions

-   Book an appointment for a patient and doctor.
-   Select date and time.
-   Record reason/visit category if needed.
-   Track scheduled, confirmed, completed, cancelled, or no-show status.
-   Filter by date, doctor, patient, and status.

### Rules

-   Appointment times must be valid.
-   A doctor should not have overlapping active appointments unless
    explicitly permitted.
-   Cancelled appointments should not block the time slot.
-   Patient and doctor IDs must refer to existing records.
-   Avoid duplicate submissions from form reruns.

An overlap check compares the proposed interval with existing active
intervals for the same doctor. A simple project can use fixed-duration
appointments; a flexible design stores start and end timestamps.

## 5.6 Admissions, wards, rooms, and beds

Keep wards, beds, and admissions in separate tables.

### Wards

-   Ward ID, name, type, floor, optional capacity.

### Beds

-   Bed ID, ward ID, bed code, operational status.
-   Operational status: available, unavailable, maintenance.

### Admissions

-   Admission ID, patient ID, bed ID, admission timestamp, discharge
    timestamp, status.

### Rules

-   The bed must exist and be operational.
-   A bed cannot have more than one active admission.
-   Discharge must close the admission and release the bed in a single
    transaction.
-   Maintenance beds cannot be assigned.
-   Bed availability depends on both operational status and active
    admissions.

A SQLite partial unique index can prevent multiple active admissions for
one bed. Service code must still validate bed status and handle
transaction failures.

## 5.7 Pharmacy and medicine inventory

A medicine catalogue and medicine batches should be separate. Different
batches of the same medicine may have different expiry dates and
quantities.

### Medicine catalogue

-   Medicine ID.
-   Name and optional generic name.
-   Strength/form, such as tablet or syrup.
-   Category and unit.
-   Reorder threshold.
-   Active/inactive status.

### Medicine batches

-   Batch ID.
-   Medicine ID.
-   Batch number.
-   Expiry date.
-   Quantity on hand.
-   Supplier.
-   Purchase/selling price if needed.
-   Received timestamp.

### Stock movements

-   Movement ID.
-   Batch ID.
-   Type: receipt, issue, return, adjustment.
-   Quantity change.
-   Timestamp.
-   User who performed the action.
-   Reference/reason.

### Functions

-   Add medicine catalogue items.
-   Receive new batches.
-   View stock by medicine and batch.
-   Issue stock and record returns/adjustments.
-   Display low-stock and near-expiry alerts.
-   Keep stock movement history.
-   Exclude expired batches from issue selection.

### Rules

-   An issue quantity must not exceed available quantity.
-   Stock must never become negative.
-   Expired batches cannot be issued.
-   Update quantity and insert movement in the same transaction.
-   Consider FEFO (first-expiry-first-out) when choosing batches.
-   Low-stock alerts should consider usable, non-expired stock across
    batches.
-   Record who changed stock and why.

For a college demo, medicine issue tracking does not imply that the
software validates treatment or prescribes medicines.

## 5.8 Suppliers and purchases

### Supplier fields

-   Supplier ID and name.
-   Contact person, phone, email, address as needed.
-   Status.

### Purchase receipt

-   Receipt ID.
-   Supplier.
-   Received date.
-   Medicine batch.
-   Quantity received.
-   Unit purchase cost.
-   Invoice reference.

When a purchase is received, create/update the appropriate batch and
record a stock movement. Do not overwrite quantity without recording the
change.

## 5.9 Billing and payments

### Bills

-   Bill ID and bill number.
-   Patient ID.
-   Related admission/appointment if applicable.
-   Bill date.
-   Subtotal, discounts, tax if applicable, total, status.

### Bill items

-   Bill item ID.
-   Bill ID.
-   Description.
-   Quantity.
-   Unit price.
-   Line total.

### Payments

-   Payment ID.
-   Bill ID.
-   Amount.
-   Payment date and method.
-   Reference if appropriate.
-   User who recorded it.

### Rules

-   Amounts cannot be negative.
-   Calculate totals from validated bill items.
-   Store money as integer minor units (for example, paise) or use a
    carefully defined decimal strategy; do not rely on binary
    floating-point for financial calculations.
-   Do not allow payments beyond the permitted balance unless
    overpayment/refund handling is supported.
-   Outstanding balance equals bill total minus accepted payments,
    adjusted for documented refunds or credits.
-   Finalized bills/payments should not be silently deleted; use
    void/correction/refund workflows.
-   Save bill header and line items in one transaction.

## 5.10 Reports and exports

Examples: - Patients registered between two dates. - Appointments by
status. - Staff attendance by date range. - Current admissions and bed
occupancy. - Low-stock and near-expiry batches. - Stock movement
history. - Bills and balances by period. - Monthly summaries.

Apply filters before export and include only necessary columns. Guard
against spreadsheet formula injection when exporting untrusted text
beginning with characters such as `=`, `+`, `-`, or `@`.

------------------------------------------------------------------------

# 6. Database Design

## 6.1 Design principles

-   Give every entity a primary key.
-   Use foreign keys for relationships.
-   Add `NOT NULL`, `UNIQUE`, and `CHECK` constraints where appropriate.
-   Store dates consistently, for example `YYYY-MM-DD`.
-   Use a documented timestamp and timezone policy.
-   Use parameterized SQL (`?` placeholders with Python `sqlite3`).
-   Enable foreign keys on every SQLite connection with
    `PRAGMA foreign_keys = ON`.
-   Use transactions for workflows that change multiple tables.
-   Keep schema initialization/migrations separate from UI code.
-   Avoid duplicating calculated values without a consistency strategy.

## 6.2 Entity relationship overview

``` text
DEPARTMENTS 1 ---- many STAFF
PATIENTS    1 ---- many APPOINTMENTS
STAFF       1 ---- many APPOINTMENTS (doctor)
PATIENTS    1 ---- many ADMISSIONS
WARDS       1 ---- many BEDS
BEDS        1 ---- many ADMISSIONS over time
MEDICINES   1 ---- many MEDICINE_BATCHES
SUPPLIERS   1 ---- many MEDICINE_BATCHES / PURCHASES
MEDICINE_BATCHES 1 ---- many STOCK_MOVEMENTS
PATIENTS    1 ---- many BILLS
BILLS       1 ---- many BILL_ITEMS
BILLS       1 ---- many PAYMENTS
USERS       1 ---- many AUDIT_LOGS
```

`STAFF` can contain all staff profiles, with a role identifying doctors,
nurses, pharmacists, and other employees. Add a doctor-specific profile
table only if doctor-specific fields are required.

## 6.3 Suggested database tables

  -----------------------------------------------------------------------
  Table                   Purpose                 Key relationships
  ----------------------- ----------------------- -----------------------
  `users`                 Login accounts and      Optional link to staff
                          roles                   

  `departments`           Standard department     Referenced by staff
                          names                   

  `staff`                 Doctors and other       Department foreign key
                          employees               

  `attendance`            Staff attendance        Staff foreign key

  `patients`              Patient registration    Appointments,
                                                  admissions, bills

  `appointments`          Scheduled visits        Patient and doctor
                                                  foreign keys

  `wards`                 Ward details            Referenced by beds

  `beds`                  Bed inventory           Ward foreign key

  `admissions`            Occupancy history       Patient and bed foreign
                                                  keys

  `medicines`             Medicine catalogue      Referenced by batches

  `suppliers`             Supplier records        Referenced by
                                                  batches/purchases

  `medicine_batches`      Batch, expiry, quantity Medicine and supplier
                                                  foreign keys

  `stock_movements`       Stock audit trail       Batch foreign key

  `purchases`             Purchase receipt header Supplier foreign key

  `purchase_items`        Items in each purchase  Purchase and
                                                  medicine/batch
                                                  references

  `bills`                 Bill header             Patient foreign key

  `bill_items`            Individual charges      Bill foreign key

  `payments`              Payments against bills  Bill foreign key

  `audit_logs`            Important changes and   User foreign key
                          actor                   
  -----------------------------------------------------------------------

## 6.4 Example initial schema

This is an illustrative starting schema, not the full schema for every
module. Add the remaining tables and constraints in later migrations.

``` sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS departments (
    department_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS patients (
    patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_code TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    date_of_birth TEXT,
    gender TEXT,
    phone TEXT,
    email TEXT,
    address TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE', 'INACTIVE')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staff (
    staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_code TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL,
    department_id INTEGER,
    phone TEXT,
    email TEXT,
    joining_date TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE', 'INACTIVE')),
    FOREIGN KEY (department_id)
        REFERENCES departments(department_id)
);

CREATE TABLE IF NOT EXISTS appointments (
    appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    doctor_id INTEGER NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'SCHEDULED'
        CHECK (status IN (
            'SCHEDULED', 'CONFIRMED', 'COMPLETED',
            'CANCELLED', 'NO_SHOW'
        )),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (end_at > start_at),
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (doctor_id) REFERENCES staff(staff_id)
);

CREATE TABLE IF NOT EXISTS wards (
    ward_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    ward_type TEXT,
    floor TEXT
);

CREATE TABLE IF NOT EXISTS beds (
    bed_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ward_id INTEGER NOT NULL,
    bed_code TEXT NOT NULL UNIQUE,
    operational_status TEXT NOT NULL DEFAULT 'AVAILABLE'
        CHECK (operational_status IN (
            'AVAILABLE', 'UNAVAILABLE', 'MAINTENANCE'
        )),
    FOREIGN KEY (ward_id) REFERENCES wards(ward_id)
);

CREATE TABLE IF NOT EXISTS admissions (
    admission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    bed_id INTEGER NOT NULL,
    admitted_at TEXT NOT NULL,
    discharged_at TEXT,
    status TEXT NOT NULL DEFAULT 'ADMITTED'
        CHECK (status IN ('ADMITTED', 'DISCHARGED', 'CANCELLED')),
    CHECK (discharged_at IS NULL OR discharged_at >= admitted_at),
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (bed_id) REFERENCES beds(bed_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS one_active_admission_per_bed
ON admissions(bed_id)
WHERE status = 'ADMITTED';

CREATE TABLE IF NOT EXISTS medicines (
    medicine_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    generic_name TEXT,
    strength TEXT,
    form TEXT,
    unit TEXT NOT NULL DEFAULT 'unit',
    reorder_level INTEGER NOT NULL DEFAULT 10
        CHECK (reorder_level >= 0),
    active INTEGER NOT NULL DEFAULT 1
        CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS medicine_batches (
    batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    medicine_id INTEGER NOT NULL,
    supplier_id INTEGER,
    batch_number TEXT NOT NULL,
    expiry_date TEXT NOT NULL,
    quantity_on_hand INTEGER NOT NULL DEFAULT 0
        CHECK (quantity_on_hand >= 0),
    purchase_price_minor INTEGER
        CHECK (purchase_price_minor IS NULL OR purchase_price_minor >= 0),
    selling_price_minor INTEGER
        CHECK (selling_price_minor IS NULL OR selling_price_minor >= 0),
    received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (medicine_id, batch_number),
    FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
);

CREATE TABLE IF NOT EXISTS stock_movements (
    movement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL,
    movement_type TEXT NOT NULL
        CHECK (movement_type IN (
            'RECEIPT', 'ISSUE', 'RETURN', 'ADJUSTMENT'
        )),
    quantity_delta INTEGER NOT NULL CHECK (quantity_delta != 0),
    reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (batch_id) REFERENCES medicine_batches(batch_id)
);
```

**Important notes** - This example does not yet define `users`,
`attendance`, `purchases`, `purchase_items`, `bills`, `bill_items`,
`payments`, or `audit_logs`. - The active-bed index prevents multiple
active admissions for one bed. Service code must still check bed
operational status and handle failures safely. - A full version should
validate appointment overlaps, medicine expiry, staff roles, and all
relevant business rules in Python services.

## 6.5 Database connection helper

``` python
import sqlite3
from pathlib import Path

DB_PATH = Path("data") / "hospital.db"

def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
```

Use short-lived connections for database operations, or a carefully
designed resource-management pattern. Close connections after use. Do
not assume one global connection is always safe across sessions and
reruns.

## 6.6 Transaction example: medicine issue

An issue changes both the batch quantity and movement history. Both
changes must succeed together.

``` python
def issue_stock(batch_id, quantity, reason):
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero")

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT quantity_on_hand, expiry_date
            FROM medicine_batches
            WHERE batch_id = ?
            """,
            (batch_id,)
        ).fetchone()

        if row is None:
            raise ValueError("Batch not found")

        # A full implementation must compare expiry_date with today's date.
        if row["quantity_on_hand"] < quantity:
            raise ValueError("Insufficient stock")

        result = conn.execute(
            """
            UPDATE medicine_batches
            SET quantity_on_hand = quantity_on_hand - ?
            WHERE batch_id = ? AND quantity_on_hand >= ?
            """,
            (quantity, batch_id, quantity)
        )

        if result.rowcount != 1:
            raise ValueError("Stock changed; please refresh and retry")

        conn.execute(
            """
            INSERT INTO stock_movements
                (batch_id, movement_type, quantity_delta, reason)
            VALUES (?, 'ISSUE', ?, ?)
            """,
            (batch_id, -quantity, reason)
        )
```

This is a teaching example, not a finished pharmacy service. The
complete service must validate expiry and permissions, handle database
exceptions, and ensure the context manager commits or rolls back
correctly. Test concurrency if multi-user operation is planned.

------------------------------------------------------------------------

# 7. UI and Dashboard Design

## 7.1 Navigation

Recommended pages:

1.  Dashboard
2.  Patients
3.  Doctors & Staff
4.  Appointments
5.  Admissions & Beds
6.  Pharmacy & Medicines
7.  Suppliers & Purchases
8.  Billing & Payments
9.  Reports
10. User Management
11. Settings / About

Use Streamlit's multipage `pages/` convention or `st.navigation`.
Maintain consistent titles, labels, and layout.

## 7.2 Dashboard wireframe

``` text
+--------------------------------------------------------------+
| MediTrack HMS                         Current User | Logout   |
+-------------------+------------------------------------------+
| SIDEBAR           | Dashboard                                |
|                   |                                          |
| Dashboard         | [Patients] [Staff] [Appointments] [Beds] |
| Patients          |                                          |
| Staff             | [Admissions Trend] [Bed Occupancy]       |
| Appointments      |                                          |
| Admissions & Beds | [Low Stock Medicines] [Expiry Alerts]    |
| Pharmacy          |                                          |
| Billing           | [Recent Appointments] [Recent Payments]  |
| Reports           |                                          |
+-------------------+------------------------------------------+
```

## 7.3 Streamlit components

-   `st.set_page_config()` --- page title and layout.
-   `st.sidebar` --- sidebar navigation controls.
-   `st.metric()` --- dashboard cards.
-   `st.form()` --- grouped inputs with explicit submission.
-   `st.dataframe()` --- browse records.
-   `st.data_editor()` --- inline editing only when changes are
    validated.
-   `st.tabs()` --- related views within a module.
-   `st.columns()` --- dashboard layout.
-   `st.date_input()` and `st.time_input()` --- date/time inputs.
-   `st.selectbox()` --- show readable labels while saving relational
    IDs.
-   `st.plotly_chart()` --- interactive charts.
-   `st.download_button()` --- filtered reports.
-   `st.session_state` --- temporary UI state and authenticated session
    information.

Never trust a client-controlled value for authorization. Check
permissions in protected service functions.

------------------------------------------------------------------------

# 8. Core Workflows

## 8.1 Register patient

``` text
Open Patients page
       |
       v
Complete form
       |
       v
Validate required fields
       |
       v
Check formats and duplicates
       |
       v
Insert with parameterized SQL
       |
       v
Commit transaction
       |
       v
Show success and refresh table
```

If validation fails, show an understandable error and do not write
incomplete data.

## 8.2 Book appointment

1.  Select an existing patient.
2.  Select an active doctor.
3.  Choose start and end time.
4.  Check that end is after start.
5.  Check overlaps with active appointments for that doctor.
6.  Save appointment and show it in the daily list.

Cancelled appointments should not block a time slot.

## 8.3 Admit patient

1.  Select patient and operational bed.
2.  Verify there is no active admission for the bed.
3.  Insert admission and update any allocation state in a single
    transaction.
4.  Refresh ward occupancy and dashboard metrics.
5.  If anything fails, roll back the changes.

## 8.4 Discharge patient

1.  Find the active admission.
2.  Confirm the selected record.
3.  Record discharge date/time and change status.
4.  Save related billing details if included.
5.  Commit changes.
6.  Recalculate bed availability.

A bed is available only if it is operational and has no active
admission.

## 8.5 Receive medicine stock

1.  Select supplier and medicine.
2.  Enter batch number, expiry date, quantity, and cost.
3.  Validate the values.
4.  Create/update the batch according to a documented rule.
5.  Record a receipt movement.
6.  Commit and refresh the inventory.

## 8.6 Issue medicine stock

1.  Select medicine and eligible batch.
2.  Confirm batch is not expired.
3.  Check quantity.
4.  Decrease stock and insert an issue movement in the same transaction.
5.  Show updated quantity and alerts.

## 8.7 Create bill

1.  Select patient.
2.  Add items, quantities, and unit prices.
3.  Validate each item.
4.  Calculate line totals and total.
5.  Save bill header and line items in one transaction.
6.  Record payments separately.
7.  Calculate the outstanding balance from accepted payments.

------------------------------------------------------------------------

# 9. Security, Privacy, and Reliability

## 9.1 Authentication and authorization

-   Require login before showing protected pages.
-   Store password hashes, never plain-text passwords.
-   Prefer a maintained password-hashing library such as Argon2 or
    bcrypt.
-   Clear authentication state on logout.
-   Apply least-privilege role permissions.
-   Check permissions in services, not only in navigation.
-   Do not commit real credentials or production secrets to GitHub.
-   Plan for session expiry and account deactivation.

## 9.2 SQL safety

Use parameterized queries:

``` python
conn.execute(
    "SELECT * FROM patients WHERE patient_id = ?",
    (patient_id,)
)
```

Do not insert raw user input into SQL strings.

## 9.3 Protect patient data

-   Use synthetic data for coursework and screenshots.
-   Avoid logging medical details, passwords, tokens, or unnecessary
    personal information.
-   Restrict exports to necessary columns.
-   Protect database and backup files.
-   Define retention and deletion rules.
-   Back up the database and test restoration.
-   Use HTTPS and a secure deployment if accessed over a network.

## 9.4 SQLite limitations

-   SQLite is file-based.
-   It supports concurrent readers well, but writes are serialized.
-   Do not place the database on an unreliable shared network drive.
-   Use SQLite's backup API or another safe backup method for an active
    database.
-   Consider PostgreSQL for multiple app instances, heavy simultaneous
    writes, or production requirements.

## 9.5 Audit history

For important changes, record: - Actor/user ID. - Action type. - Entity
type and ID. - Timestamp. - Minimal description.

Avoid storing unnecessary sensitive medical information in audit logs.
Ordinary users should not be able to casually edit or delete audit
history.

------------------------------------------------------------------------

# 10. Validation and Error Handling

  -----------------------------------------------------------------------
  Data / operation                    Validation
  ----------------------------------- -----------------------------------
  Patient                             Name required, valid date of birth,
                                      documented phone rule

  Staff                               Name and role required, valid
                                      department/status

  Appointment                         Existing patient and doctor, end
                                      after start, no prohibited overlap

  Bed assignment                      Operational bed and no active
                                      admission

  Discharge                           Existing active admission,
                                      discharge not before admission

  Medicine batch                      Existing medicine, batch number,
                                      valid expiry date

  Stock receipt                       Positive quantity, valid supplier
                                      and batch

  Stock issue                         Positive quantity, sufficient
                                      stock, batch not expired

  Bill                                Valid patient and line items,
                                      non-negative amounts

  Payment                             Valid bill, positive amount,
                                      permitted balance rules

  Login                               Valid credentials and role
                                      permission
  -----------------------------------------------------------------------

Catch expected errors and show a useful message. Log technical
diagnostics without revealing internals to users. Never silently ignore
failed writes.

------------------------------------------------------------------------

# 11. Development Roadmap

## Phase 0 --- Requirements and planning

**Tasks** - Confirm the college requirements. - Decide roles and
essential modules. - Draw a use-case diagram and ER diagram. - Define
fields and validation rules. - Separate must-have features from optional
features.

**Deliverables:** problem statement, objectives, scope, diagrams, module
list, timeline.

**Done when:** every feature has a user, inputs, expected result, and
validation rules.

## Phase 1 --- Environment and skeleton

**Tasks** - Install Python. - Create a virtual environment. - Install
Streamlit, pandas, Plotly, and optional libraries. - Create folders and
a basic landing page. - Set up Git and `.gitignore`.

Windows Command Prompt:

``` bat
mkdir hospital_management
cd hospital_management
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install streamlit pandas plotly openpyxl pytest
```

Create `requirements.txt` after testing. A starting list:

``` text
streamlit
pandas
plotly
openpyxl
pytest
```

Pin tested versions before final submission for reproducibility.

**Done when:** `streamlit run app.py` opens the application without
errors.

## Phase 2 --- Database foundation

-   Create `database.py`.
-   Initialize tables and constraints.
-   Enable foreign keys.
-   Add synthetic seed data.
-   Add schema versioning/migrations.
-   Test persistence after restart.

**Done when:** saved records remain after closing and reopening the app.

## Phase 3 --- Patients

-   Registration form.
-   Search and filters.
-   View/update/archive.
-   Validation and error handling.
-   History links as later modules become available.

**Done when:** create, read, update, and archive all work.

## Phase 4 --- Staff and departments

-   Department management.
-   Staff CRUD and filtering.
-   Attendance if in scope.

**Done when:** staff can be assigned to valid departments and filtered
correctly.

## Phase 5 --- Appointments

-   Booking form.
-   Overlap checks.
-   Status updates.
-   Daily and doctor-specific views.

**Done when:** invalid and prohibited overlapping bookings are rejected.

## Phase 6 --- Beds and admissions

-   Wards and beds.
-   Occupancy view.
-   Admission/discharge transactions.
-   Active-bed protection.

**Done when:** one bed cannot be assigned to two active admissions.

## Phase 7 --- Pharmacy and suppliers

-   Medicine catalogue.
-   Suppliers and batches.
-   Receipt and issue operations.
-   Stock movement history.
-   Low-stock and expiry alerts.

**Done when:** stock never becomes negative, expired batches cannot be
issued, and movement records reconcile with quantity.

## Phase 8 --- Billing and payments

-   Bills and bill items.
-   Total calculations.
-   Payments and balance calculations.
-   Date filters and reports.

**Done when:** totals and outstanding balances match test cases.

## Phase 9 --- Dashboard and reports

-   Database-driven metrics.
-   Interactive charts.
-   Date filters.
-   Safe CSV/Excel exports.
-   Empty states.

**Done when:** dashboard values match SQL results and exports respect
filters.

## Phase 10 --- Authentication and permissions

-   User accounts and password hashing.
-   Role-based permissions.
-   Protect all write operations.
-   Test denied access.
-   Logout and session behavior.

**Done when:** users cannot perform operations outside their role,
including through direct navigation.

## Phase 11 --- Testing and submission

-   Functional tests and error tests.
-   Backup/restore test.
-   Synthetic demo data.
-   Screenshots of the running system.
-   README, report, and viva preparation.

**Done when:** a clean installation works by following the README and
the main workflows pass the test checklist.

------------------------------------------------------------------------

# 12. Testing Plan

  -----------------------------------------------------------------------
  Test ID                 Scenario                Expected result
  ----------------------- ----------------------- -----------------------
  T01                     Register patient with   Saved and visible in
                          valid data              list

  T02                     Submit blank patient    Error; no row created
                          name                    

  T03                     Search for a patient    Matching records shown

  T04                     Appointment end before  Rejected
                          start                   

  T05                     Overlapping appointment Rejected if overlap is
                          for same doctor         prohibited

  T06                     Admit to available bed  Active admission saved

  T07                     Assign second patient   Rejected
                          to occupied bed         

  T08                     Discharge active        Admission closes and
                          admission               bed may be reused

  T09                     Receive medicine batch  Quantity and receipt
                                                  movement saved

  T10                     Issue within stock      Quantity decreases and
                          quantity                movement is saved

  T11                     Issue more than         Rejected; quantity
                          available stock         unchanged

  T12                     Issue expired batch     Rejected

  T13                     Create bill with valid  Correct total stored
                          items                   

  T14                     Record valid payment    Balance recalculated

  T15                     Search with no match    Clear empty-state
                                                  message

  T16                     Open empty dashboard    No crash; zero/empty
                                                  states shown

  T17                     Unauthorized protected  Denied
                          operation               

  T18                     Restart application     Saved data remains

  T19                     Restore backup in test  Expected records
                          environment             restored

  T20                     Export filtered report  Only selected
                                                  records/columns
                                                  exported
  -----------------------------------------------------------------------

### Testing levels

-   **Unit tests:** business rules and calculations.
-   **Integration tests:** service functions and SQLite transactions.
-   **UI tests:** forms, navigation, filters, and empty states.
-   **Regression tests:** re-run important tests after changes.
-   **Acceptance tests:** demonstrate workflows and verify expected
    outcomes.

Use a temporary test database so automated tests do not modify the main
demo data.

------------------------------------------------------------------------

# 13. Dashboard Metric Definitions

  -----------------------------------------------------------------------
  Metric                              Suggested definition
  ----------------------------------- -----------------------------------
  Total patients                      Count patient records, with
                                      active/inactive handling documented

  Active staff                        Staff whose employment status is
                                      active

  Today's appointments                Appointments starting today and
                                      included statuses

  Current admissions                  Admissions whose status is
                                      `ADMITTED`

  Occupied beds                       Beds with a valid active admission

  Available beds                      Operational beds with no active
                                      admission

  Low-stock medicines                 Active medicines whose usable,
                                      non-expired stock is at/below
                                      reorder threshold

  Expiring batches                    Positive-stock batches expiring
                                      within configured warning period

  Total billed                        Sum of finalized bills in selected
                                      period

  Payments received                   Sum of accepted payments in
                                      selected period

  Outstanding balance                 Valid bill totals minus accepted
                                      payments, adjusted for supported
                                      credits/refunds
  -----------------------------------------------------------------------

Document whether expiry warnings include today and whether low-stock
comparisons use `<` or `<=`.

------------------------------------------------------------------------

# 14. Common Mistakes to Avoid

1.  **One giant `app.py`:** split code as features grow.
2.  **SQL duplicated in every page:** centralize queries and business
    rules.
3.  **Raw SQL interpolation:** use parameterized queries.
4.  **Missing foreign keys:** enable and define relationships.
5.  **One quantity field for all medicine stock:** use batches and stock
    movements.
6.  **Deleting historical records:** use status, void, correction, and
    audit workflows.
7.  **No transaction for multi-table changes:** partial writes can break
    workflow state.
8.  **Saving names instead of IDs for relationships:** show labels but
    save IDs.
9.  **Hard-coded metrics:** query SQLite.
10. **Plain-text passwords:** store secure hashes.
11. **Hiding menus as the only security measure:** check permissions in
    services.
12. **Committing private database files:** keep real data out of source
    control.
13. **Inconsistent date/time storage:** choose and document a policy.
14. **No synthetic seed data:** prepare reliable demo records.
15. **Claiming unimplemented features:** distinguish implemented,
    partial, and planned features.

------------------------------------------------------------------------

# 15. Git and GitHub

Example `.gitignore`:

``` gitignore
.venv/
__pycache__/
*.py[cod]
.env
data/hospital.db
data/backups/
.pytest_cache/
.streamlit/secrets.toml
```

Use a seed script to generate fictional data rather than committing a
database with private information.

Suggested commit sequence:

1.  `Initial Streamlit project`
2.  `Add SQLite schema and helpers`
3.  `Implement patient management`
4.  `Implement staff and departments`
5.  `Add appointments and scheduling rules`
6.  `Add admissions and bed workflows`
7.  `Add pharmacy batches and stock movements`
8.  `Add billing and payments`
9.  `Add dashboard reports and exports`
10. `Add authentication and permissions`
11. `Add tests and documentation`

README should include setup, screenshots, implemented features, schema,
known limitations, and safe demo instructions.

------------------------------------------------------------------------

# 16. Running the Application

From the project folder:

``` bat
.venv\Scripts\activate
streamlit run app.py
```

Streamlit normally opens a browser tab. If not, use the local URL
printed in the terminal, commonly `http://localhost:8501`.

Stop the app with `Ctrl+C` in the terminal.

For a clean setup on another computer: 1. Install a compatible Python
version. 2. Clone/download the project. 3. Create and activate the
virtual environment. 4. Install dependencies from `requirements.txt`. 5.
Initialize or migrate the database. 6. Create a local demo administrator
using a safe setup procedure. 7. Run the app. 8. Follow the README
test/demo instructions.

Do not distribute a real administrator password or a database containing
actual patient records.

------------------------------------------------------------------------

# 17. College Project Report Structure

1.  **Abstract** --- problem, proposed solution, technology, and
    outcome.
2.  **Introduction** --- hospital operations and centralized tracking.
3.  **Problem Statement** --- limitations of manual/disconnected
    records.
4.  **Objectives and Scope** --- what the system will and will not do.
5.  **Existing and Proposed Systems** --- compare workflows without
    unsupported claims.
6.  **Requirement Analysis** --- functional and non-functional
    requirements.
7.  **System Architecture** --- UI, service, repository, and database
    layers.
8.  **Database Design** --- ER diagram, schema, keys, relationships.
9.  **Module Design** --- module purpose and workflows.
10. **Implementation** --- Streamlit pages, Python services, SQL,
    validation.
11. **Testing** --- test cases, expected and actual results.
12. **Results and Screenshots** --- only from the real running
    application.
13. **Limitations and Future Work** --- scalability, security,
    deployment, integrations.
14. **Conclusion** --- what was actually achieved.
15. **References** --- official documentation and relevant sources.

Do not invent test results or show screenshots of features that have not
been implemented.

------------------------------------------------------------------------

# 18. Viva Questions and Answers

**Q1. What is Streamlit?**\
Streamlit is a Python framework for building interactive web
applications, particularly data-oriented apps, using Python code.

**Q2. Why use SQLite?**\
SQLite is a lightweight relational database stored in a file. It is easy
to configure and suitable for a small local project.

**Q3. What is CRUD?**\
Create, Read, Update, and Delete---the basic operations for managing
records.

**Q4. What is a primary key?**\
A column or set of columns that uniquely identifies a row.

**Q5. What is a foreign key?**\
A constraint that links a record to a related record and helps preserve
referential integrity.

**Q6. Why use parameterized SQL?**\
It separates query structure from user values, reduces SQL injection
risk, and safely handles values.

**Q7. What is a transaction?**\
A group of database operations treated as one unit. If it fails, changes
can be rolled back rather than leaving partial state.

**Q8. Why separate medicine batches from medicines?**\
The same medicine can have multiple batches with different expiry dates,
quantities, and costs.

**Q9. How is bed availability calculated?**\
A bed must be operational and have no active admission. Historical
admissions do not imply current occupancy.

**Q10. How are low-stock alerts generated?**\
The application compares usable stock against a defined reorder
threshold.

**Q11. What is the difference between UI and business logic?**\
The UI collects input and displays output. Business logic validates
operations and enforces rules independently of the page layout.

**Q12. Why might SQLite not suit a large hospital deployment?**\
It is file-based and serializes writes. Large multi-user workloads and
multiple app instances may require a server database and
production-grade infrastructure.

**Q13. How do you protect patient information?**\
Use synthetic demo data, authentication, role-based authorization,
secure password hashing, parameterized queries, limited exports,
backups, and appropriate deployment controls.

**Q14. Why does Streamlit rerun code?**\
Many user interactions trigger script execution again. Persistent
records belong in SQLite; temporary UI state can be held in session
state.

**Q15. What future improvements are possible?**\
PostgreSQL deployment, stronger audit/monitoring, automated backups,
expanded permissions, integrations, and professional security/privacy
review.

------------------------------------------------------------------------

# 19. Official Documentation

-   Python: https://docs.python.org/3/
-   Python `sqlite3`: https://docs.python.org/3/library/sqlite3.html
-   SQLite: https://www.sqlite.org/docs.html
-   Streamlit: https://docs.streamlit.io/
-   Streamlit API reference:
    https://docs.streamlit.io/develop/api-reference
-   pandas: https://pandas.pydata.org/docs/
-   Plotly Python: https://plotly.com/python/
-   pytest: https://docs.pytest.org/

------------------------------------------------------------------------

# 20. Recommended Build Order and Definition of Done

Build in this order:

1.  Project setup and working Streamlit home page.
2.  SQLite connection, schema, and synthetic seed data.
3.  Patient CRUD and search.
4.  Staff and department management.
5.  Appointment booking and status management.
6.  Ward/bed management and admission/discharge.
7.  Medicine catalogue, batches, stock receipts/issues, and alerts.
8.  Suppliers and purchase receipts.
9.  Billing, bill items, and payments.
10. Database-driven dashboard and charts.
11. Authentication, role checks, and audit logging.
12. Exports, tests, backup/restore, screenshots, README, and report.

**Definition of done:** A feature is complete only when its form works,
its data persists in SQLite, validation is enforced, related workflows
remain consistent, errors are handled, and the feature has been tested.
A dashboard that only displays cards is not a complete hospital
management system.
