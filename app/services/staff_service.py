from datetime import date

from database import read_connection, transaction
from repositories import staff_repository
from services import audit_service
from utils import clock
from utils import validators as v
from utils.permissions import has_permission, require

STAFF_ROLES = ("DOCTOR", "NURSE", "PHARMACIST", "RECEPTIONIST", "ADMINISTRATOR", "BILLING",
               "LAB_TECHNICIAN", "OTHER")
ATTENDANCE_STATUSES = ("PRESENT", "ABSENT", "LEAVE", "HALF_DAY")


# --- departments -----------------------------------------------------------

def list_departments(user=None):
    with read_connection() as conn:
        return staff_repository.list_departments(conn)


def save_department(user, name, description=None, department_id=None) -> int:
    require(user, "staff.edit")
    name = v.required_text(name, "Department name", max_len=80)
    description = v.clean_text(description, max_len=300)
    with transaction() as conn:
        clash = [d for d in staff_repository.list_departments(conn)
                 if d["name"].lower() == name.lower() and d["department_id"] != department_id]
        if clash:
            raise v.ValidationError(f"Department '{name}' already exists.")
        if department_id:
            staff_repository.update_department(conn, department_id, name, description)
            audit_service.log(conn, user, "UPDATE", "department", department_id)
            return department_id
        new_id = staff_repository.insert_department(conn, name, description)
        audit_service.log(conn, user, "CREATE", "department", new_id)
        return new_id


# --- staff -----------------------------------------------------------------

def _clean(conn, data: dict) -> dict:
    joining = data.get("joining_date")
    if isinstance(joining, date):
        joining = v.past_or_today(joining, "Joining date").isoformat()
    department_id = data.get("department_id") or None
    if department_id and staff_repository.get_department(conn, department_id) is None:
        raise v.ValidationError("Selected department does not exist.")
    return {
        "full_name": v.required_text(data.get("full_name"), "Staff name", max_len=100),
        "role": v.choice(data.get("role"), STAFF_ROLES, "Role"),
        "department_id": department_id,
        "specialization": v.clean_text(data.get("specialization"), max_len=100),
        "phone": v.phone(data.get("phone")),
        "email": v.email(data.get("email")),
        "joining_date": joining or None,
        "status": v.choice(data.get("status") or "ACTIVE", ("ACTIVE", "INACTIVE"), "Status"),
    }


def create(user, data: dict) -> dict:
    require(user, "staff.edit")
    with transaction() as conn:
        clean = _clean(conn, data)
        staff_id = staff_repository.insert(conn, clean)
        audit_service.log(conn, user, "CREATE", "staff", staff_id, clean["role"])
        return staff_repository.get(conn, staff_id)


def update(user, staff_id: int, data: dict) -> dict:
    require(user, "staff.edit")
    with transaction() as conn:
        if staff_repository.get(conn, staff_id) is None:
            raise v.ValidationError("Staff member not found.")
        clean = _clean(conn, data)
        staff_repository.update(conn, staff_id, clean)
        audit_service.log(conn, user, "UPDATE", "staff", staff_id)
        return staff_repository.get(conn, staff_id)


def search(user, term=None, role=None, department_id=None, status=None):
    require(user, "staff.view")
    with read_connection() as conn:
        return staff_repository.search(conn, (term or "").strip() or None, role,
                                       department_id, status)


def get(user, staff_id):
    require(user, "staff.view")
    with read_connection() as conn:
        return staff_repository.get(conn, staff_id)


def doctor_options(user=None, active_only=True):
    """Doctors are needed by booking and admission screens."""
    with read_connection() as conn:
        return staff_repository.options(conn, role="DOCTOR", active_only=active_only)


def staff_options(user, active_only=False):
    if not (has_permission(user, "staff.view") or has_permission(user, "users.manage")):
        require(user, "staff.view")
    with read_connection() as conn:
        return staff_repository.options(conn, active_only=active_only)


# --- attendance ------------------------------------------------------------

def mark_attendance(user, staff_id, attendance_date: date, status, check_in=None,
                    check_out=None, notes=None):
    require(user, "attendance.edit")
    status = v.choice(status, ATTENDANCE_STATUSES, "Attendance status")
    if attendance_date > clock.today():
        raise v.ValidationError("Attendance cannot be recorded for a future date.")
    check_in = check_in.strftime("%H:%M") if check_in else None
    check_out = check_out.strftime("%H:%M") if check_out else None
    if status in ("ABSENT", "LEAVE"):
        check_in = check_out = None
    if check_in and check_out and check_out < check_in:
        raise v.ValidationError("Check-out time cannot be before check-in time.")
    with transaction() as conn:
        member = staff_repository.get(conn, staff_id)
        if member is None or member["status"] != "ACTIVE":
            raise v.ValidationError("Attendance can only be recorded for active staff.")
        staff_repository.upsert_attendance(conn, staff_id, attendance_date.isoformat(), status,
                                           check_in, check_out,
                                           v.clean_text(notes, max_len=200))
        audit_service.log(conn, user, "ATTENDANCE", "staff", staff_id,
                          f"{attendance_date.isoformat()} {status}")


def attendance_sheet(user, attendance_date: date):
    require(user, "staff.view")
    with read_connection() as conn:
        return staff_repository.attendance_for_date(conn, attendance_date.isoformat())


def attendance_between(user, date_from: date, date_to: date, staff_id=None):
    require(user, "staff.view")
    with read_connection() as conn:
        return staff_repository.attendance_between(conn, date_from.isoformat(),
                                                   date_to.isoformat(), staff_id)
