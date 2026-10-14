"""Bills, line items and payments. All money is integer paise.

Balance = bill total - accepted payments. Void bills have no balance.
Finalized bills and payments are never deleted: they are voided with a reason.
"""

from dataclasses import dataclass
from datetime import date, datetime

from database import read_connection, transaction
from repositories import admission_repository, appointment_repository, billing_repository
from repositories import patient_repository
from services import audit_service
from utils import clock
from utils import validators as v
from utils.formatting import money, percent_of
from utils.permissions import require

PAYMENT_METHODS = ("CASH", "CARD", "UPI", "INSURANCE", "BANK_TRANSFER")


@dataclass
class BillLine:
    description: str
    quantity: int
    unit_price_minor: int


def calculate(lines: list[BillLine], discount_minor: int = 0, tax_basis_points: int = 0) -> dict:
    """Validate lines and compute totals. Tax applies after discount."""
    if not lines:
        raise v.ValidationError("A bill needs at least one item.")
    clean = []
    for i, line in enumerate(lines, start=1):
        desc = v.required_text(line.description, f"Item {i} description", max_len=150)
        qty = v.positive_int(line.quantity, f"Item {i} quantity")
        price = v.money_minor(line.unit_price_minor, f"Item {i} unit price")
        clean.append(BillLine(desc, qty, price))
    subtotal = sum(l.quantity * l.unit_price_minor for l in clean)
    discount = v.money_minor(discount_minor, "Discount")
    if discount > subtotal:
        raise v.ValidationError("Discount cannot exceed the subtotal.")
    tax_bp = v.non_negative_int(tax_basis_points, "Tax rate")
    if tax_bp > 10000:
        raise v.ValidationError("Tax rate cannot exceed 100%.")
    tax = percent_of(subtotal - discount, tax_bp)
    return {"lines": clean, "subtotal": subtotal, "discount": discount, "tax": tax,
            "total": subtotal - discount + tax}


def create_bill(user, patient_id, lines: list[BillLine], *, discount_minor=0,
                tax_basis_points=0, bill_date: date | None = None, admission_id=None,
                appointment_id=None, notes=None) -> dict:
    """Save header and items in one transaction."""
    require(user, "billing.edit")
    calc = calculate(lines, discount_minor, tax_basis_points)
    bill_date = v.past_or_today(bill_date or clock.today(), "Bill date")
    with transaction() as conn:
        if patient_repository.get(conn, patient_id) is None:
            raise v.ValidationError("Select an existing patient.")
        if admission_id:
            adm = admission_repository.get_admission(conn, admission_id)
            if adm is None or adm["patient_id"] != patient_id:
                raise v.ValidationError("The admission does not belong to this patient.")
        if appointment_id:
            appt = appointment_repository.get(conn, appointment_id)
            if appt is None or appt["patient_id"] != patient_id:
                raise v.ValidationError("The appointment does not belong to this patient.")
        bill_id = billing_repository.insert_bill(
            conn, patient_id, admission_id, appointment_id, bill_date.isoformat(),
            calc["subtotal"], calc["discount"], calc["tax"], calc["total"],
            v.clean_text(notes, max_len=300), user["user_id"])
        for line in calc["lines"]:
            billing_repository.insert_item(conn, bill_id, line.description, line.quantity,
                                           line.unit_price_minor)
        audit_service.log(conn, user, "CREATE", "bill", bill_id, money(calc["total"]))
        return billing_repository.get_bill(conn, bill_id)


def record_payment(user, bill_id, amount_minor, method, reference=None,
                   paid_at: datetime | None = None) -> int:
    require(user, "billing.edit")
    amount_minor = v.money_minor(amount_minor, "Payment amount", allow_zero=False)
    v.choice(method, PAYMENT_METHODS, "Payment method")
    paid_at = paid_at or clock.now()
    if paid_at > clock.now():
        raise v.ValidationError("Payment time cannot be in the future.")
    with transaction() as conn:
        bill = billing_repository.get_bill(conn, bill_id)
        if bill is None:
            raise v.ValidationError("Bill not found.")
        if bill["status"] != "FINAL":
            raise v.ValidationError("Payments cannot be recorded against a void bill.")
        if amount_minor > bill["balance_minor"]:
            # Overpayment/refunds are not supported in this version.
            raise v.ValidationError(
                f"Payment exceeds the outstanding balance of {money(bill['balance_minor'])}.")
        payment_id = billing_repository.insert_payment(
            conn, bill_id, amount_minor, clock.ts(paid_at), method,
            v.clean_text(reference, max_len=60), user["user_id"])
        audit_service.log(conn, user, "PAYMENT", "bill", bill_id, money(amount_minor))
        return payment_id


def void_payment(user, payment_id, reason):
    require(user, "billing.edit")
    reason = v.required_text(reason, "Reason", max_len=200)
    with transaction() as conn:
        if billing_repository.void_payment(conn, payment_id, reason) != 1:
            raise v.ValidationError("Only an accepted payment can be voided.")
        audit_service.log(conn, user, "VOID", "payment", payment_id)


def void_bill(user, bill_id, reason):
    require(user, "billing.edit")
    reason = v.required_text(reason, "Reason", max_len=200)
    with transaction() as conn:
        bill = billing_repository.get_bill(conn, bill_id)
        if bill is None or bill["status"] != "FINAL":
            raise v.ValidationError("Only a final bill can be voided.")
        if bill["paid_minor"] > 0:
            raise v.ValidationError("Void the bill's payments before voiding the bill.")
        billing_repository.void_bill(conn, bill_id, reason)
        audit_service.log(conn, user, "VOID", "bill", bill_id)


def get_bill(user, bill_id) -> dict | None:
    require(user, "billing.view")
    with read_connection() as conn:
        bill = billing_repository.get_bill(conn, bill_id)
        if bill:
            bill["items"] = billing_repository.items(conn, bill_id)
            bill["payments"] = billing_repository.payments_for_bill(conn, bill_id)
        return bill


def search(user, date_from=None, date_to=None, patient_id=None, status=None,
           outstanding_only=False):
    require(user, "billing.view")
    with read_connection() as conn:
        return billing_repository.search(conn, date_from.isoformat() if date_from else None,
                                         date_to.isoformat() if date_to else None, patient_id,
                                         status, outstanding_only)


def payments(user, date_from=None, date_to=None):
    require(user, "billing.view")
    with read_connection() as conn:
        return billing_repository.payments(conn, date_from.isoformat() if date_from else None,
                                           date_to.isoformat() if date_to else None)


def billable_context(user, patient_id):
    """Admissions and appointments a new bill can be linked to."""
    require(user, "billing.view")
    with read_connection() as conn:
        return {
            "admissions": admission_repository.search(conn, patient_id=patient_id),
            "appointments": appointment_repository.search(conn, patient_id=patient_id),
        }
