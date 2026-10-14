from datetime import date, timedelta

import pytest

from database import transaction
from services import pharmacy_service
from services.pharmacy_service import ReceiptLine
from utils.validators import ValidationError

TODAY = date.today()


@pytest.fixture
def supplier(admin):
    return pharmacy_service.save_supplier(admin, {"name": "Test Supplies"})


@pytest.fixture
def medicine(admin):
    return pharmacy_service.save_medicine(admin, {"name": "Paracetamol", "strength": "500 mg",
                                                  "form": "Tablet", "reorder_level": 20})


def receive(admin, supplier, medicine, batch, qty, days=365):
    return pharmacy_service.receive_stock(
        admin, supplier, TODAY, "INV-1",
        [ReceiptLine(medicine, batch, TODAY + timedelta(days=days), qty, 150, 200)])


def on_hand(admin, medicine):
    return {b["batch_number"]: b["quantity_on_hand"]
            for b in pharmacy_service.batches(admin, medicine)}


def test_t09_receive_creates_batch_and_movement(admin, supplier, medicine):
    receive(admin, supplier, medicine, "b1", 100)
    assert on_hand(admin, medicine) == {"B1": 100}
    moves = pharmacy_service.movements(admin)
    assert [(m["movement_type"], m["quantity_delta"]) for m in moves] == [("RECEIPT", 100)]
    assert pharmacy_service.purchases(admin)[0]["quantity"] == 100


def test_receive_same_batch_adds_and_requires_same_expiry(admin, supplier, medicine):
    receive(admin, supplier, medicine, "B1", 100)
    receive(admin, supplier, medicine, "B1", 50)
    assert on_hand(admin, medicine) == {"B1": 150}
    with pytest.raises(ValidationError, match="expiry date must match"):
        receive(admin, supplier, medicine, "B1", 10, days=200)


def test_receive_expired_batch_rejected(admin, supplier, medicine):
    with pytest.raises(ValidationError, match="expired"):
        receive(admin, supplier, medicine, "OLD", 10, days=0)


def test_t10_issue_within_stock(admin, supplier, medicine):
    receive(admin, supplier, medicine, "B1", 100)
    batch = pharmacy_service.batches(admin, medicine)[0]
    pharmacy_service.issue_from_batch(admin, batch["batch_id"], 30, "Ward issue")
    assert on_hand(admin, medicine) == {"B1": 70}


def test_t11_issue_more_than_available_rejected(admin, supplier, medicine):
    receive(admin, supplier, medicine, "B1", 10)
    batch = pharmacy_service.batches(admin, medicine)[0]
    with pytest.raises(ValidationError, match="Only 10"):
        pharmacy_service.issue_from_batch(admin, batch["batch_id"], 11, "Ward issue")
    assert on_hand(admin, medicine) == {"B1": 10}
    assert len(pharmacy_service.movements(admin)) == 1


def test_t12_issue_expired_batch_rejected(admin, supplier, medicine):
    receive(admin, supplier, medicine, "B1", 10)
    with transaction() as conn:
        conn.execute("UPDATE medicine_batches SET expiry_date = ?",
                     ((TODAY - timedelta(days=1)).isoformat(),))
    batch = pharmacy_service.batches(admin, medicine)[0]
    with pytest.raises(ValidationError, match="expired"):
        pharmacy_service.issue_from_batch(admin, batch["batch_id"], 1, "Ward issue")
    with pytest.raises(ValidationError, match="Only 0 usable"):
        pharmacy_service.issue_fefo(admin, medicine, 1, "Ward issue")


def test_fefo_uses_earliest_expiry_first(admin, supplier, medicine):
    receive(admin, supplier, medicine, "LATE", 50, days=300)
    receive(admin, supplier, medicine, "EARLY", 20, days=60)
    taken = pharmacy_service.issue_fefo(admin, medicine, 30, "Ward issue")
    assert taken == [("EARLY", 20), ("LATE", 10)]
    assert on_hand(admin, medicine) == {"EARLY": 0, "LATE": 40}


def test_return_and_adjust_rules(admin, supplier, medicine):
    receive(admin, supplier, medicine, "B1", 10)
    bid = pharmacy_service.batches(admin, medicine)[0]["batch_id"]
    pharmacy_service.issue_from_batch(admin, bid, 4, "Ward")
    with pytest.raises(ValidationError, match="more than was issued"):
        pharmacy_service.return_to_stock(admin, bid, 5, "Unused")
    pharmacy_service.return_to_stock(admin, bid, 4, "Unused")
    with pytest.raises(ValidationError, match="negative"):
        pharmacy_service.adjust_stock(admin, bid, -11, "Stock take")
    pharmacy_service.adjust_stock(admin, bid, -2, "Damaged")
    assert on_hand(admin, medicine) == {"B1": 8}


def test_stock_never_negative_at_database_level(admin, supplier, medicine):
    import sqlite3
    receive(admin, supplier, medicine, "B1", 5)
    with pytest.raises(sqlite3.IntegrityError):
        with transaction() as conn:
            conn.execute("UPDATE medicine_batches SET quantity_on_hand = -1")


def test_movements_reconcile_with_quantities(admin, supplier, medicine):
    receive(admin, supplier, medicine, "B1", 40)
    receive(admin, supplier, medicine, "B2", 40, days=100)
    pharmacy_service.issue_fefo(admin, medicine, 50, "Ward")
    bid = pharmacy_service.batches(admin, medicine)[0]["batch_id"]
    pharmacy_service.return_to_stock(admin, bid, 5, "Unused")
    assert pharmacy_service.reconciliation_mismatches(admin) == []


def test_low_stock_and_expiry_alerts(admin, supplier, medicine):
    receive(admin, supplier, medicine, "SOON", 15, days=30)    # usable 15 <= reorder 20
    alerts = pharmacy_service.alerts(admin)
    assert [m["medicine_id"] for m in alerts["low_stock"]] == [medicine]
    assert [b["batch_number"] for b in alerts["near_expiry"]] == ["SOON"]
    receive(admin, supplier, medicine, "LATER", 10, days=400)  # usable 25 > 20
    assert pharmacy_service.alerts(admin)["low_stock"] == []


def test_expired_stock_does_not_count_as_usable(admin, supplier, medicine):
    receive(admin, supplier, medicine, "B1", 100)
    with transaction() as conn:
        conn.execute("UPDATE medicine_batches SET expiry_date = ?",
                     ((TODAY - timedelta(days=1)).isoformat(),))
    row = pharmacy_service.stock_summary(admin)[0]
    assert row["usable_stock"] == 0 and row["expired_stock"] == 100 and row["low_stock"]
