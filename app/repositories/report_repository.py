"""Read-only report queries that span several modules."""

from repositories.common import many


def patients_registered(conn, date_from, date_to):
    return many(conn, "SELECT patient_code, full_name, gender, date_of_birth, phone, status,"
                      " created_at AS registered_at FROM patients"
                      " WHERE created_at BETWEEN ? AND ? ORDER BY created_at",
                (f"{date_from} 00:00:00", f"{date_to} 23:59:59"))


def appointments_by_status(conn, date_from, date_to):
    return many(conn, "SELECT status, COUNT(*) AS appointments FROM appointments"
                      " WHERE start_at BETWEEN ? AND ? GROUP BY status ORDER BY appointments DESC",
                (f"{date_from} 00:00:00", f"{date_to} 23:59:59"))


def attendance_summary(conn, date_from, date_to):
    return many(conn, "SELECT s.staff_code, s.full_name, s.role,"
                      " SUM(a.status = 'PRESENT') AS present, SUM(a.status = 'HALF_DAY') AS half_day,"
                      " SUM(a.status = 'LEAVE') AS leave, SUM(a.status = 'ABSENT') AS absent"
                      " FROM attendance a JOIN staff s ON s.staff_id = a.staff_id"
                      " WHERE a.attendance_date BETWEEN ? AND ?"
                      " GROUP BY s.staff_id ORDER BY s.full_name", (date_from, date_to))


def monthly_summary(conn, month_from):
    return many(conn, """
        WITH months AS (
            SELECT substr(created_at, 1, 7) AS month FROM patients WHERE created_at >= :m
            UNION SELECT substr(start_at, 1, 7) FROM appointments WHERE start_at >= :m
            UNION SELECT substr(admitted_at, 1, 7) FROM admissions WHERE admitted_at >= :m
            UNION SELECT substr(bill_date, 1, 7) FROM bills WHERE bill_date >= :m
        )
        SELECT month,
          (SELECT COUNT(*) FROM patients WHERE substr(created_at, 1, 7) = month) AS new_patients,
          (SELECT COUNT(*) FROM appointments WHERE substr(start_at, 1, 7) = month
             AND status = 'COMPLETED') AS completed_appointments,
          (SELECT COUNT(*) FROM admissions WHERE substr(admitted_at, 1, 7) = month
             AND status != 'CANCELLED') AS admissions,
          (SELECT COALESCE(SUM(total_minor), 0) FROM bills WHERE substr(bill_date, 1, 7) = month
             AND status = 'FINAL') AS billed_minor,
          (SELECT COALESCE(SUM(amount_minor), 0) FROM payments
             WHERE substr(paid_at, 1, 7) = month AND status = 'ACCEPTED') AS collected_minor
        FROM months ORDER BY month""", {"m": month_from})
