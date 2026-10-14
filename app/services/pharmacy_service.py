"""Medicine catalogue, batches, stock movements, suppliers and purchases.

Invariants:
* every quantity change writes a stock_movements row in the same transaction,
  so SUM(quantity_delta) per batch always equals quantity_on_hand;
* stock never becomes negative (CHECK constraint + guarded UPDATE);
* expired batches are never issued; issues default to FEFO.
"""

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

import config
from database import read_connection, transaction
from repositories import pharmacy_repository as repo
from services import audit_service
from utils import clock
from utils import validators as v
from utils.permissions import require

FORMS = ("Tablet", "Capsule", "Syrup", "Injection", "Ointment", "Drops", "Inhaler", "Other")
MOVEMENT_TYPES = ("RECEIPT", "ISSUE", "RETURN", "ADJUSTMENT")


# --- catalogue -------------------------------------------------------------

def _clean_medicine(data):
    return {
        "name": v.required_text(data.get("name"), "Medicine name", max_len=100),
        "generic_name": v.clean_text(data.get("generic_name"), max_len=100),
        "strength": v.clean_text(data.get("strength"), max_len=40),
        "form": v.clean_text(data.get("form"), max_len=40),
        "category": v.clean_text(data.get("category"), max_len=60),
        "unit": v.required_text(data.get("unit") or "unit", "Unit", max_len=20),
        "reorder_level": v.non_negative_int(data.get("reorder_level", 10), "Reorder level"),
        "active": 1 if data.get("active", True) else 0,
    }


def save_medicine(user, data, medicine_id=None) -> int:
    require(user, "pharmacy.edit")
    clean = _clean_medicine(data)
    with transaction() as conn:
        try:
            if medicine_id:
                if repo.get_medicine(conn, medicine_id) is None:
                    raise v.ValidationError("Medicine not found.")
                repo.update_medicine(conn, medicine_id, clean)
                audit_service.log(conn, user, "UPDATE", "medicine", medicine_id)
                return medicine_id
            new_id = repo.insert_medicine(conn, clean)
        except sqlite3.IntegrityError:
            raise v.ValidationError("A medicine with this name, strength and form already exists.") from None
        audit_service.log(conn, user, "CREATE", "medicine", new_id, clean["name"])
        return new_id


def stock_summary(user, term=None, active_only=False):
    require(user, "pharmacy.view")
    with read_connection() as conn:
        rows = repo.stock_summary(conn, clock.ds(), (term or "").strip() or None, active_only)
    for r in rows:
        r["low_stock"] = bool(r["active"]) and r["usable_stock"] <= r["reorder_level"]
    return rows


def medicine_options(user, active_only=True):
    require(user, "pharmacy.view")
    with read_connection() as conn:
        return repo.medicine_options(conn, active_only)


def batches(user, medicine_id=None, in_stock_only=False, usable_only=False):
    require(user, "pharmacy.view")
    with read_connection() as conn:
        return repo.batches(conn, medicine_id, in_stock_only,
                            clock.ds() if usable_only else None)


# --- receiving -------------------------------------------------------------

@dataclass
class ReceiptLine:
    medicine_id: int
    batch_number: str
    expiry_date: date
    quantity: int
    unit_cost_minor: int
    selling_price_minor: int | None = None


def receive_stock(user, supplier_id, received_date: date, invoice_reference,
                  lines: list[ReceiptLine]) -> int:
    """Record a purchase receipt. Rule for batches: if (medicine, batch number)
    already exists the expiry date must match and quantity is added to it;
    otherwise a new batch is created. Returns the purchase id."""
    require(user, "pharmacy.edit")
    if not lines:
        raise v.ValidationError("Add at least one item to the receipt.")
    v.past_or_today(received_date, "Received date")
    invoice_reference = v.clean_text(invoice_reference, max_len=60)
    with transaction() as conn:
        supplier = repo.get_supplier(conn, supplier_id)
        if supplier is None or supplier["status"] != "ACTIVE":
            raise v.ValidationError("Select an existing, active supplier.")
        purchase_id = repo.insert_purchase(conn, supplier_id, received_date.isoformat(),
                                           invoice_reference, user["user_id"])
        for line in lines:
            qty = v.positive_int(line.quantity, "Quantity")
            cost = v.money_minor(line.unit_cost_minor, "Unit cost")
            if line.selling_price_minor is not None:
                v.money_minor(line.selling_price_minor, "Selling price")
            batch_number = v.required_text(line.batch_number, "Batch number", max_len=40).upper()
            if line.expiry_date <= clock.today():
                raise v.ValidationError(f"Batch {batch_number} is already expired.")
            medicine = repo.get_medicine(conn, line.medicine_id)
            if medicine is None or not medicine["active"]:
                raise v.ValidationError("Select an existing, active medicine.")
            batch = repo.find_batch(conn, line.medicine_id, batch_number)
            if batch is None:
                batch_id = repo.insert_batch(conn, line.medicine_id, supplier_id, batch_number,
                                             line.expiry_date.isoformat(), cost,
                                             line.selling_price_minor)
            else:
                if batch["expiry_date"] != line.expiry_date.isoformat():
                    raise v.ValidationError(
                        f"Batch {batch_number} exists with expiry {batch['expiry_date']}; "
                        "the expiry date must match.")
                batch_id = batch["batch_id"]
                repo.update_batch_prices(conn, batch_id, cost, line.selling_price_minor)
            repo.change_quantity(conn, batch_id, qty)
            repo.insert_movement(conn, batch_id, "RECEIPT", qty, "Purchase receipt",
                                 invoice_reference or f"PUR-{purchase_id}", user["user_id"])
            repo.insert_purchase_item(conn, purchase_id, batch_id, qty, cost)
        audit_service.log(conn, user, "RECEIVE", "purchase", purchase_id,
                          f"{len(lines)} item(s)")
        return purchase_id


# --- issue / return / adjust -----------------------------------------------

def _apply(conn, user, batch_id, movement_type, delta, reason, reference):
    if repo.change_quantity(conn, batch_id, delta) != 1:
        raise v.ValidationError("Insufficient stock in the batch; refresh and retry.")
    repo.insert_movement(conn, batch_id, movement_type, delta, reason, reference,
                         user["user_id"])


def issue_from_batch(user, batch_id, quantity, reason, reference=None):
    require(user, "pharmacy.edit")
    quantity = v.positive_int(quantity, "Quantity")
    reason = v.required_text(reason, "Reason", max_len=200)
    with transaction() as conn:
        batch = repo.get_batch(conn, batch_id)
        if batch is None:
            raise v.ValidationError("Batch not found.")
        if batch["expiry_date"] < clock.ds():
            raise v.ValidationError(f"Batch {batch['batch_number']} expired on "
                                    f"{batch['expiry_date']} and cannot be issued.")
        if batch["quantity_on_hand"] < quantity:
            raise v.ValidationError(
                f"Only {batch['quantity_on_hand']} available in batch {batch['batch_number']}.")
        _apply(conn, user, batch_id, "ISSUE", -quantity, reason, v.clean_text(reference))
        audit_service.log(conn, user, "ISSUE", "batch", batch_id, f"qty {quantity}")


def issue_fefo(user, medicine_id, quantity, reason, reference=None) -> list[tuple[str, int]]:
    """Issue across non-expired batches, earliest expiry first.
    Returns [(batch_number, quantity)] actually taken from each batch."""
    require(user, "pharmacy.edit")
    quantity = v.positive_int(quantity, "Quantity")
    reason = v.required_text(reason, "Reason", max_len=200)
    with transaction() as conn:
        usable = repo.batches(conn, medicine_id, in_stock_only=True, usable_from=clock.ds())
        available = sum(b["quantity_on_hand"] for b in usable)
        if available < quantity:
            raise v.ValidationError(f"Only {available} usable unit(s) in stock.")
        taken, remaining = [], quantity
        for batch in usable:
            if remaining == 0:
                break
            take = min(remaining, batch["quantity_on_hand"])
            _apply(conn, user, batch["batch_id"], "ISSUE", -take, reason,
                   v.clean_text(reference))
            taken.append((batch["batch_number"], take))
            remaining -= take
        audit_service.log(conn, user, "ISSUE", "medicine", medicine_id, f"qty {quantity} FEFO")
        return taken


def return_to_stock(user, batch_id, quantity, reason, reference=None):
    require(user, "pharmacy.edit")
    quantity = v.positive_int(quantity, "Quantity")
    reason = v.required_text(reason, "Reason", max_len=200)
    with transaction() as conn:
        batch = repo.get_batch(conn, batch_id)
        if batch is None:
            raise v.ValidationError("Batch not found.")
        total_issued, total_returned = repo.issued_and_returned(conn, batch_id)
        if quantity > total_issued - total_returned:
            raise v.ValidationError("Cannot return more than was issued from this batch.")
        _apply(conn, user, batch_id, "RETURN", quantity, reason, v.clean_text(reference))
        audit_service.log(conn, user, "RETURN", "batch", batch_id, f"qty {quantity}")


def adjust_stock(user, batch_id, delta, reason):
    """Stock-take correction, damage or disposal of expired stock (negative delta)."""
    require(user, "pharmacy.edit")
    if not isinstance(delta, int) or delta == 0:
        raise v.ValidationError("Adjustment must be a non-zero whole number.")
    reason = v.required_text(reason, "Reason", max_len=200)
    with transaction() as conn:
        batch = repo.get_batch(conn, batch_id)
        if batch is None:
            raise v.ValidationError("Batch not found.")
        if batch["quantity_on_hand"] + delta < 0:
            raise v.ValidationError(
                f"Adjustment would make stock negative (on hand {batch['quantity_on_hand']}).")
        _apply(conn, user, batch_id, "ADJUSTMENT", delta, reason, None)
        audit_service.log(conn, user, "ADJUST", "batch", batch_id, f"delta {delta}")


# --- alerts & history ------------------------------------------------------

def alerts(user, warning_days: int = config.EXPIRY_WARNING_DAYS) -> dict:
    """Low stock: active medicine whose usable (non-expired) stock <= reorder level.
    Near expiry: positive-stock batch expiring from today (inclusive) to today+N."""
    require(user, "pharmacy.view")
    today = clock.today()
    with read_connection() as conn:
        summary = repo.stock_summary(conn, today.isoformat(), active_only=True)
        return {
            "low_stock": [r for r in summary if r["usable_stock"] <= r["reorder_level"]],
            "near_expiry": repo.expiring_batches(conn, today.isoformat(),
                                                 (today + timedelta(days=warning_days)).isoformat()),
            "expired": repo.expired_batches(conn, today.isoformat()),
        }


def movements(user, date_from=None, date_to=None, medicine_id=None, movement_type=None):
    require(user, "pharmacy.view")
    with read_connection() as conn:
        return repo.movements(conn, date_from.isoformat() if date_from else None,
                              date_to.isoformat() if date_to else None, medicine_id,
                              movement_type)


def reconciliation_mismatches(user):
    require(user, "pharmacy.view")
    with read_connection() as conn:
        return repo.reconciliation_mismatches(conn)


# --- suppliers -------------------------------------------------------------

def save_supplier(user, data, supplier_id=None) -> int:
    require(user, "suppliers.edit")
    clean = {
        "name": v.required_text(data.get("name"), "Supplier name", max_len=100),
        "contact_person": v.clean_text(data.get("contact_person"), max_len=100),
        "phone": v.phone(data.get("phone")),
        "email": v.email(data.get("email")),
        "address": v.clean_text(data.get("address"), max_len=300),
        "status": v.choice(data.get("status") or "ACTIVE", ("ACTIVE", "INACTIVE"), "Status"),
    }
    with transaction() as conn:
        try:
            if supplier_id:
                repo.update_supplier(conn, supplier_id, clean)
                audit_service.log(conn, user, "UPDATE", "supplier", supplier_id)
                return supplier_id
            new_id = repo.insert_supplier(conn, clean)
        except sqlite3.IntegrityError:
            raise v.ValidationError(f"Supplier '{clean['name']}' already exists.") from None
        audit_service.log(conn, user, "CREATE", "supplier", new_id)
        return new_id


def list_suppliers(user, active_only=False):
    require(user, "suppliers.view")
    with read_connection() as conn:
        return repo.list_suppliers(conn, active_only)


def purchases(user, supplier_id=None, date_from=None, date_to=None):
    require(user, "suppliers.view")
    with read_connection() as conn:
        return repo.purchases(conn, supplier_id, date_from.isoformat() if date_from else None,
                              date_to.isoformat() if date_to else None)
