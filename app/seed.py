"""Create fictional demo data. All names, phones and records are synthetic.

Usage:
    python seed.py            # seed an empty database
    python seed.py --reset    # delete the database file and seed again

Demo accounts (fictional, for demonstrations only - change them before any
real use):
"""

import argparse
import random
from datetime import datetime, time, timedelta

import config
import database
from database import transaction
from services import (admission_service, appointment_service, auth_service, billing_service,
                      patient_service, pharmacy_service, staff_service)
from services.billing_service import BillLine
from services.pharmacy_service import ReceiptLine
from utils import clock

DEMO_USERS = [
    # username, password, role, full name, staff role link
    ("admin", "Admin@123", "ADMIN", "Asha Rao (Admin)", None),
    ("reception", "Reception@123", "RECEPTIONIST", "Rahul Mehta", "RECEPTIONIST"),
    ("pharmacist", "Pharma@123", "PHARMACIST", "Neha Kapoor", "PHARMACIST"),
    ("billing", "Billing@123", "BILLING", "Vikram Singh", "BILLING"),
    ("doctor", "Doctor@123", "DOCTOR", "Dr. Ananya Iyer", "DOCTOR"),
    ("nurse", "Nurse@123", "NURSE", "Priya Nair", "NURSE"),
]
__doc__ += "\n".join(f"    {u:<11} {p}  ({r})" for u, p, r, _, _ in DEMO_USERS) + "\n"

FIRST = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Krishna", "Ishaan",
         "Rohan", "Ananya", "Diya", "Aadhya", "Saanvi", "Myra", "Kiara", "Meera", "Riya",
         "Kavya", "Tara", "Nikhil", "Pooja", "Sneha", "Karan", "Farhan", "Zoya", "Imran",
         "Gurpreet", "Simran", "Joseph", "Maria", "Lakshmi", "Suresh", "Divya", "Manoj"]
LAST = ["Sharma", "Verma", "Gupta", "Reddy", "Nair", "Iyer", "Das", "Bose", "Khan", "Singh",
        "Patel", "Joshi", "Menon", "Pillai", "Chopra", "Malhotra", "Fernandes", "Mukherjee"]
DEPARTMENTS = [
    ("General Medicine", "Outpatient and inpatient adult care"),
    ("Pediatrics", "Care for infants, children and adolescents"),
    ("Orthopedics", "Bones, joints and musculoskeletal care"),
    ("Cardiology", "Heart and circulatory system"),
    ("Pharmacy", "Medicine dispensing and inventory"),
    ("Laboratory", "Diagnostics and pathology"),
    ("Administration", "Front office, billing and management"),
]
DOCTORS = [
    ("Dr. Ananya Iyer", "General Medicine", "Internal medicine"),
    ("Dr. Rajesh Kumar", "Cardiology", "Interventional cardiology"),
    ("Dr. Sunita Menon", "Pediatrics", "Neonatology"),
    ("Dr. Arvind Bose", "Orthopedics", "Joint replacement"),
    ("Dr. Fatima Sheikh", "General Medicine", "Diabetology"),
    ("Dr. Karthik Reddy", "Cardiology", "Electrophysiology"),
]
OTHER_STAFF = [
    ("Priya Nair", "NURSE", "General Medicine"), ("Lakshmi Pillai", "NURSE", "Pediatrics"),
    ("Joseph Thomas", "NURSE", "Orthopedics"), ("Maria Fernandes", "NURSE", "Cardiology"),
    ("Neha Kapoor", "PHARMACIST", "Pharmacy"), ("Imran Qureshi", "PHARMACIST", "Pharmacy"),
    ("Rahul Mehta", "RECEPTIONIST", "Administration"),
    ("Vikram Singh", "BILLING", "Administration"),
    ("Asha Rao", "ADMINISTRATOR", "Administration"),
    ("Deepak Joshi", "LAB_TECHNICIAN", "Laboratory"),
]
WARDS = [("General Ward A", "General", "1", 8, 150000), ("General Ward B", "General", "1", 8, 150000),
         ("Pediatric Ward", "Pediatric", "2", 6, 180000), ("ICU", "Intensive care", "3", 4, 650000),
         ("Private Rooms", "Private", "4", 5, 400000)]
SUPPLIERS = [("MediSupply Distributors", "Anil Gupta"), ("HealthLine Pharma", "Sara Khan"),
             ("CarePlus Wholesale", "Mohan Das"), ("Apex Medical Traders", "Ritu Verma")]
MEDICINES = [
    # name, generic, strength, form, category, unit, reorder
    ("Paracetamol", "Acetaminophen", "500 mg", "Tablet", "Analgesic", "tablet", 200),
    ("Ibuprofen", "Ibuprofen", "400 mg", "Tablet", "Analgesic", "tablet", 150),
    ("Amoxicillin", "Amoxicillin", "500 mg", "Capsule", "Antibiotic", "capsule", 120),
    ("Azithromycin", "Azithromycin", "250 mg", "Tablet", "Antibiotic", "tablet", 80),
    ("Cetirizine", "Cetirizine", "10 mg", "Tablet", "Antihistamine", "tablet", 100),
    ("Metformin", "Metformin", "500 mg", "Tablet", "Antidiabetic", "tablet", 200),
    ("Amlodipine", "Amlodipine", "5 mg", "Tablet", "Cardiovascular", "tablet", 150),
    ("Atorvastatin", "Atorvastatin", "10 mg", "Tablet", "Cardiovascular", "tablet", 120),
    ("Omeprazole", "Omeprazole", "20 mg", "Capsule", "Gastrointestinal", "capsule", 120),
    ("ORS Sachet", "Oral rehydration salts", "21 g", "Other", "Gastrointestinal", "sachet", 100),
    ("Cough Syrup", "Dextromethorphan", "100 ml", "Syrup", "Respiratory", "bottle", 40),
    ("Salbutamol Inhaler", "Salbutamol", "100 mcg", "Inhaler", "Respiratory", "inhaler", 20),
    ("Insulin Glargine", "Insulin glargine", "100 IU/ml", "Injection", "Antidiabetic", "vial", 25),
    ("Ceftriaxone", "Ceftriaxone", "1 g", "Injection", "Antibiotic", "vial", 40),
    ("Povidone Iodine", "Povidone iodine", "5%", "Ointment", "Antiseptic", "tube", 30),
]
REASONS = ["Fever and cough", "Routine check-up", "Follow-up visit", "Chest pain review",
           "Knee pain", "Blood pressure review", "Diabetes review", "Child vaccination",
           "Back pain", "Skin rash", "Headache", "Post-operative review"]


def _name(rng):
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def _phone(rng):
    return "9" + "".join(str(rng.randint(0, 9)) for _ in range(9))


def seed_demo(seed: int = 42, verbose: bool = False) -> dict:
    """Populate an empty database. Uses the service layer so every business
    rule applies to demo data too. Dates are relative to today."""
    rng = random.Random(seed)
    database.init_db()
    if not database.is_empty():
        raise RuntimeError("Database already has users; refusing to seed.")

    def say(msg):
        if verbose:
            print(msg)

    today = clock.today()
    now = clock.now()

    # --- users & departments ------------------------------------------------
    u0 = DEMO_USERS[0]
    admin_id = auth_service.create_first_admin(u0[0], u0[3], u0[1])
    admin = auth_service.load_user(admin_id)
    dept = {name: staff_service.save_department(admin, name, desc)
            for name, desc in DEPARTMENTS}
    say("departments")

    # --- staff ---------------------------------------------------------------
    staff_ids = {}
    doctor_ids = []
    for name, dname, spec in DOCTORS:
        s = staff_service.create(admin, {
            "full_name": name, "role": "DOCTOR", "department_id": dept[dname],
            "specialization": spec, "phone": _phone(rng),
            "email": name.lower().replace("dr. ", "").replace(" ", ".") + "@meditrack.example",
            "joining_date": today - timedelta(days=rng.randint(200, 3000))})
        staff_ids[name] = s["staff_id"]
        doctor_ids.append(s["staff_id"])
    for name, role, dname in OTHER_STAFF:
        s = staff_service.create(admin, {
            "full_name": name, "role": role, "department_id": dept[dname],
            "phone": _phone(rng), "joining_date": today - timedelta(days=rng.randint(100, 2500))})
        staff_ids[name] = s["staff_id"]
    say("staff")

    for username, password, role, full_name, staff_role in DEMO_USERS[1:]:
        staff_name = full_name if full_name in staff_ids else None
        auth_service.create_user(admin, username, full_name, password, role,
                                 staff_ids.get(staff_name))
    say("users")

    # --- attendance (last 7 days) ------------------------------------------
    for back in range(7, -1, -1):
        day = today - timedelta(days=back)
        if day.weekday() == 6:
            continue
        for sid in staff_ids.values():
            status = rng.choices(["PRESENT", "HALF_DAY", "LEAVE", "ABSENT"], [85, 5, 6, 4])[0]
            cin = time(8 + rng.randint(0, 1), rng.choice([0, 15, 30, 45]))
            cout = time(16 + rng.randint(0, 2), rng.choice([0, 15, 30, 45]))
            if back == 0:
                cout = None
            staff_service.mark_attendance(admin, sid, day, status, cin, cout)
    say("attendance")

    # --- patients ------------------------------------------------------------
    patient_ids = []
    created_dates = {}
    for i in range(48):
        dob = today - timedelta(days=rng.randint(365 * 1, 365 * 85))
        gender = rng.choice(["MALE", "FEMALE"])
        p = patient_service.register(admin, {
            "full_name": _name(rng), "date_of_birth": dob, "gender": gender,
            "blood_group": rng.choice(patient_service.BLOOD_GROUPS), "phone": _phone(rng),
            "address": f"{rng.randint(1, 200)}, {rng.choice(['MG Road', 'Park Street', 'Lake View', 'Station Road', 'Gandhi Nagar'])}",
            "emergency_contact": f"{_name(rng)} - {_phone(rng)}"}, allow_duplicate=True)
        patient_ids.append(p["patient_id"])
        created_dates[p["patient_id"]] = now - timedelta(days=rng.randint(0, 170),
                                                         hours=rng.randint(0, 8))
    # Spread registration dates over the past months (seed-only backdating).
    with transaction() as conn:
        for pid, created in created_dates.items():
            conn.execute("UPDATE patients SET created_at = ? WHERE patient_id = ?",
                         (clock.ts(created), pid))
        conn.execute("UPDATE patients SET status = 'INACTIVE' WHERE patient_id = ?",
                     (patient_ids[-1],))
    active_patients = patient_ids[:-1]
    say("patients")

    # --- appointments: past 14 days to next 7 days ---------------------------
    slots = [time(h, m) for h in range(9, 17) for m in (0, 30) if h != 13]
    appointment_ids = []
    for offset in range(-14, 8):
        day = today + timedelta(days=offset)
        if day.weekday() == 6:
            continue
        for doctor_id in doctor_ids:
            for slot in rng.sample(slots, rng.randint(2, 5)):
                start = datetime.combine(day, slot)
                if offset >= 0 and start < now:
                    continue
                end = start + timedelta(minutes=rng.choice([15, 20, 30]))
                appt = appointment_service.book(admin, rng.choice(active_patients), doctor_id,
                                                start, end, rng.choice(REASONS),
                                                allow_past=True)
                appointment_ids.append(appt["appointment_id"])
                if end < now:
                    status = rng.choices(["COMPLETED", "NO_SHOW", "CANCELLED"], [82, 8, 10])[0]
                    appointment_service.update_status(admin, appt["appointment_id"], status)
                elif rng.random() < 0.35:
                    appointment_service.update_status(admin, appt["appointment_id"], "CONFIRMED")
                elif rng.random() < 0.06:
                    appointment_service.update_status(admin, appt["appointment_id"], "CANCELLED")
    say(f"appointments: {len(appointment_ids)}")

    # --- wards, beds, admissions --------------------------------------------
    bed_ids = []
    for wname, wtype, floor, beds, rate in WARDS:
        ward_id = admission_service.add_ward(admin, wname, wtype, floor)
        prefix = "".join(w[0] for w in wname.split()).upper()
        for n in range(1, beds + 1):
            bed_ids.append(admission_service.add_bed(admin, ward_id, f"{prefix}-{n:02d}", rate))
    admission_service.set_bed_status(admin, bed_ids[7], "MAINTENANCE")
    admission_service.set_bed_status(admin, bed_ids[-1], "UNAVAILABLE")

    pool = rng.sample(active_patients, 30)
    discharged = []
    # Historical (discharged) admissions over the last month.
    for pid in pool[:16]:
        bed = rng.choice(admission_service.available_beds(admin))
        admitted = now - timedelta(days=rng.randint(4, 30), hours=rng.randint(0, 12))
        adm = admission_service.admit(admin, pid, bed["bed_id"], admitted,
                                      rng.choice(doctor_ids), rng.choice(REASONS))
        out = admitted + timedelta(days=rng.randint(1, 3), hours=rng.randint(1, 10))
        bill_id = admission_service.discharge(admin, adm["admission_id"], min(out, now),
                                              "Stable at discharge", create_bed_bill=True)
        discharged.append(bill_id)
    # Currently admitted patients.
    for pid in pool[16:30]:
        beds = admission_service.available_beds(admin)
        if not beds:
            break
        bed = rng.choice(beds)
        admitted = now - timedelta(days=rng.randint(0, 5), hours=rng.randint(1, 20))
        admission_service.admit(admin, pid, bed["bed_id"], admitted, rng.choice(doctor_ids),
                                rng.choice(REASONS))
    say("admissions")

    # --- suppliers & stock ---------------------------------------------------
    supplier_ids = [pharmacy_service.save_supplier(admin, {
        "name": name, "contact_person": contact, "phone": _phone(rng),
        "email": name.split()[0].lower() + "@supplier.example"}) for name, contact in SUPPLIERS]
    med_ids = []
    for name, generic, strength, form, cat, unit, reorder in MEDICINES:
        med_ids.append(pharmacy_service.save_medicine(admin, {
            "name": name, "generic_name": generic, "strength": strength, "form": form,
            "category": cat, "unit": unit, "reorder_level": reorder}))
    for i, mid in enumerate(med_ids):
        reorder = MEDICINES[i][6]
        price = rng.choice([150, 250, 400, 900, 1500, 4500, 12000])
        n_batches = rng.randint(1, 3)
        for b in range(n_batches):
            # Medicine #3 and #11 get a batch expiring soon; others last longer.
            days_to_expiry = rng.randint(20, 80) if (i in (3, 11) and b == 0) else rng.randint(150, 720)
            qty = rng.randint(reorder // 2, reorder * 3)
            if i in (6, 12):  # deliberately low stock for the alert demo
                qty = max(1, reorder // 4)
            pharmacy_service.receive_stock(
                admin, rng.choice(supplier_ids), today - timedelta(days=rng.randint(5, 60)),
                f"INV-{rng.randint(10000, 99999)}",
                [ReceiptLine(mid, f"B{rng.randint(1000, 9999)}{chr(65 + b)}",
                             today + timedelta(days=days_to_expiry), qty, price,
                             int(price * 1.25))])
    # One batch that has since expired: receive it, then backdate its expiry
    # (a receipt for an already-expired batch is correctly rejected).
    pid = pharmacy_service.receive_stock(
        admin, supplier_ids[0], today - timedelta(days=200), "INV-OLD-001",
        [ReceiptLine(med_ids[4], "EXP001", today + timedelta(days=1), 40, 200, 250)])
    with transaction() as conn:
        conn.execute("UPDATE medicine_batches SET expiry_date = ? WHERE batch_number = 'EXP001'",
                     ((today - timedelta(days=10)).isoformat(),))
    del pid
    # Some issues so movement history is not just receipts.
    for mid in rng.sample(med_ids, 10):
        usable = sum(b["quantity_on_hand"] for b in pharmacy_service.batches(
            admin, mid, in_stock_only=True, usable_only=True))
        if usable > 10:
            pharmacy_service.issue_fefo(admin, mid, rng.randint(1, min(30, usable // 2)),
                                        "Ward issue", f"WARD-{rng.randint(1, 5)}")
    say("pharmacy")

    # --- billing -------------------------------------------------------------
    for appt_id in rng.sample(appointment_ids, min(30, len(appointment_ids))):
        with database.read_connection() as conn:
            appt = conn.execute("SELECT * FROM appointments WHERE appointment_id = ?",
                                (appt_id,)).fetchone()
        if appt["status"] != "COMPLETED":
            continue
        lines = [BillLine("Consultation fee", 1, rng.choice([50000, 70000, 100000]))]
        if rng.random() < 0.5:
            lines.append(BillLine("Blood test panel", 1, rng.choice([45000, 80000])))
        if rng.random() < 0.4:
            lines.append(BillLine("Medicines", rng.randint(1, 3), rng.choice([12000, 25000])))
        bill = billing_service.create_bill(
            admin, appt["patient_id"], lines, tax_basis_points=rng.choice([0, 500, 1200]),
            discount_minor=rng.choice([0, 0, 0, 5000]),
            bill_date=clock.parse_date(appt["start_at"]), appointment_id=appt_id)
        _pay(admin, rng, bill, clock.parse_ts(appt["end_at"]), now)
    for bill_id in discharged:
        if bill_id:
            bill = billing_service.get_bill(admin, bill_id)
            _pay(admin, rng, bill, clock.parse_ts(bill["bill_date"] + " 18:00:00"), now)
    say("billing")
    return {"admin_id": admin_id}


def _pay(admin, rng, bill, when, now):
    roll = rng.random()
    when = min(when + timedelta(hours=1), now)
    if roll < 0.65:
        billing_service.record_payment(admin, bill["bill_id"], bill["balance_minor"],
                                       rng.choice(["CASH", "CARD", "UPI"]), paid_at=when)
    elif roll < 0.85:
        part = (bill["balance_minor"] // 2) or bill["balance_minor"]
        billing_service.record_payment(admin, bill["bill_id"], part, "UPI",
                                       f"UPI{rng.randint(100000, 999999)}", paid_at=when)


def reset_demo() -> None:
    """Delete the database file and re-create the demo data."""
    path = config.get_db_path()
    for suffix in ("", "-wal", "-shm", "-journal"):
        p = path.with_name(path.name + suffix)
        if p.exists():
            p.unlink()
    seed_demo()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed MediTrack with fictional demo data.")
    parser.add_argument("--reset", action="store_true", help="delete the database first")
    args = parser.parse_args()
    if args.reset:
        reset_demo()
    else:
        seed_demo(verbose=True)
    print(f"Demo data ready in {config.get_db_path()}")
    print(__doc__[__doc__.index("Demo accounts"):])
