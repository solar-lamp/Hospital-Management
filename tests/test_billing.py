import pytest

from services import billing_service
from services.billing_service import BillLine
from utils.formatting import money, to_minor
from utils.validators import ValidationError


def lines():
    return [BillLine("Consultation", 1, 50000), BillLine("Blood test", 2, 12550)]


def test_t13_bill_totals(admin, patient):
    bill = billing_service.create_bill(admin, patient["patient_id"], lines(),
                                       discount_minor=5100, tax_basis_points=1800)
    # subtotal 750.00 + 2*125.50 = 751.00 -> 75100; after discount 70000; tax 18% = 12600
    assert bill["subtotal_minor"] == 75100
    assert bill["tax_minor"] == 12600
    assert bill["total_minor"] == 75100 - 5100 + 12600
    assert bill["balance_minor"] == bill["total_minor"]
    assert bill["bill_number"].startswith("BILL-")
    assert len(billing_service.get_bill(admin, bill["bill_id"])["items"]) == 2


def test_tax_rounding_half_up():
    calc = billing_service.calculate([BillLine("Item", 1, 1005)], 0, 500)  # 5% of 10.05
    assert calc["tax"] == 50                                          # 0.5025 -> 0.50
    calc = billing_service.calculate([BillLine("Item", 1, 1010)], 0, 500)
    assert calc["tax"] == 51                                          # 0.505 -> 0.51


def test_money_conversion_avoids_float_errors():
    assert to_minor(0.1 + 0.2) == 30
    assert to_minor("1234.565") == 123457
    assert money(123456) == "₹1,234.56"


@pytest.mark.parametrize("bad, message", [
    ([], "at least one item"),
    ([BillLine("", 1, 100)], "description"),
    ([BillLine("X", 0, 100)], "quantity"),
    ([BillLine("X", 1, -1)], "unit price"),
])
def test_invalid_items_rejected(admin, patient, bad, message):
    with pytest.raises(ValidationError, match=message):
        billing_service.create_bill(admin, patient["patient_id"], bad)


def test_discount_cannot_exceed_subtotal(admin, patient):
    with pytest.raises(ValidationError, match="Discount"):
        billing_service.create_bill(admin, patient["patient_id"], lines(), discount_minor=10**7)


def test_t14_payments_update_balance(admin, patient):
    bill = billing_service.create_bill(admin, patient["patient_id"], lines())
    billing_service.record_payment(admin, bill["bill_id"], 25100, "CASH")
    assert billing_service.get_bill(admin, bill["bill_id"])["balance_minor"] == 50000
    with pytest.raises(ValidationError, match="exceeds the outstanding balance"):
        billing_service.record_payment(admin, bill["bill_id"], 50001, "UPI")
    with pytest.raises(ValidationError, match="greater than zero"):
        billing_service.record_payment(admin, bill["bill_id"], 0, "UPI")
    billing_service.record_payment(admin, bill["bill_id"], 50000, "UPI")
    assert billing_service.get_bill(admin, bill["bill_id"])["balance_minor"] == 0


def test_void_payment_restores_balance_and_void_bill_rules(admin, patient):
    bill = billing_service.create_bill(admin, patient["patient_id"], lines())
    pay = billing_service.record_payment(admin, bill["bill_id"], 10000, "CARD")
    with pytest.raises(ValidationError, match="payments before"):
        billing_service.void_bill(admin, bill["bill_id"], "Wrong patient")
    billing_service.void_payment(admin, pay, "Card declined")
    assert billing_service.get_bill(admin, bill["bill_id"])["balance_minor"] == bill["total_minor"]
    billing_service.void_bill(admin, bill["bill_id"], "Wrong patient")
    voided = billing_service.get_bill(admin, bill["bill_id"])
    assert voided["status"] == "VOID" and voided["balance_minor"] == 0
    with pytest.raises(ValidationError, match="void bill"):
        billing_service.record_payment(admin, bill["bill_id"], 100, "CASH")


def test_bill_header_and_items_are_atomic(admin, patient, monkeypatch):
    from repositories import billing_repository
    from database import read_connection

    def boom(*args, **kwargs):
        raise RuntimeError("disk failure")
    monkeypatch.setattr(billing_repository, "insert_item", boom)
    with pytest.raises(RuntimeError):
        billing_service.create_bill(admin, patient["patient_id"], lines())
    with read_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM bills").fetchone()[0] == 0
