from repositories.common import like, many, one, scalar
from utils import clock

MEDICINE_FIELDS = ("name", "generic_name", "strength", "form", "category", "unit",
                   "reorder_level", "active")
SUPPLIER_FIELDS = ("name", "contact_person", "phone", "email", "address", "status")


# --- medicines -------------------------------------------------------------

def insert_medicine(conn, data):
    return conn.execute(
        f"INSERT INTO medicines ({', '.join(MEDICINE_FIELDS)})"
        f" VALUES ({', '.join('?' for _ in MEDICINE_FIELDS)})",
        [data.get(f) for f in MEDICINE_FIELDS],
    ).lastrowid


def update_medicine(conn, medicine_id, data):
    conn.execute(f"UPDATE medicines SET {', '.join(f'{f} = ?' for f in MEDICINE_FIELDS)}"
                 " WHERE medicine_id = ?", (*[data.get(f) for f in MEDICINE_FIELDS], medicine_id))


def get_medicine(conn, medicine_id):
    return one(conn, "SELECT * FROM medicines WHERE medicine_id = ?", (medicine_id,))


def stock_summary(conn, today, term=None, active_only=False):
    """One row per medicine with usable (non-expired) and expired stock."""
    sql = ("SELECT m.medicine_id, m.name, m.generic_name, m.strength, m.form, m.category,"
           " m.unit, m.reorder_level, m.active,"
           " COALESCE(SUM(CASE WHEN b.expiry_date >= ? THEN b.quantity_on_hand END), 0)"
           "   AS usable_stock,"
           " COALESCE(SUM(CASE WHEN b.expiry_date < ? THEN b.quantity_on_hand END), 0)"
           "   AS expired_stock,"
           " MIN(CASE WHEN b.expiry_date >= ? AND b.quantity_on_hand > 0 THEN b.expiry_date END)"
           "   AS next_expiry"
           " FROM medicines m LEFT JOIN medicine_batches b ON b.medicine_id = m.medicine_id"
           " WHERE 1 = 1")
    params: list = [today, today, today]
    if term:
        sql += " AND (m.name LIKE ? ESCAPE '\\' OR m.generic_name LIKE ? ESCAPE '\\')"
        params += [like(term)] * 2
    if active_only:
        sql += " AND m.active = 1"
    return many(conn, sql + " GROUP BY m.medicine_id ORDER BY m.name", params)


def medicine_options(conn, active_only=True):
    sql = "SELECT medicine_id, name, strength, form, unit FROM medicines"
    if active_only:
        sql += " WHERE active = 1"
    return many(conn, sql + " ORDER BY name")


# --- batches ---------------------------------------------------------------

BATCH_SELECT = (
    "SELECT b.batch_id, b.medicine_id, m.name AS medicine, m.strength, m.form, m.category,"
    " b.batch_number, b.expiry_date, b.quantity_on_hand, b.purchase_price_minor,"
    " b.selling_price_minor, b.received_at, b.supplier_id, s.name AS supplier"
    " FROM medicine_batches b JOIN medicines m ON m.medicine_id = b.medicine_id"
    " LEFT JOIN suppliers s ON s.supplier_id = b.supplier_id"
)


def get_batch(conn, batch_id):
    return one(conn, BATCH_SELECT + " WHERE b.batch_id = ?", (batch_id,))


def find_batch(conn, medicine_id, batch_number):
    return one(conn, BATCH_SELECT + " WHERE b.medicine_id = ? AND b.batch_number = ?",
               (medicine_id, batch_number))


def insert_batch(conn, medicine_id, supplier_id, batch_number, expiry_date,
                 purchase_price_minor, selling_price_minor):
    return conn.execute(
        "INSERT INTO medicine_batches (medicine_id, supplier_id, batch_number, expiry_date,"
        " quantity_on_hand, purchase_price_minor, selling_price_minor, received_at)"
        " VALUES (?, ?, ?, ?, 0, ?, ?, ?)",
        (medicine_id, supplier_id, batch_number, expiry_date, purchase_price_minor,
         selling_price_minor, clock.ts()),
    ).lastrowid


def update_batch_prices(conn, batch_id, purchase_price_minor, selling_price_minor):
    conn.execute("UPDATE medicine_batches SET purchase_price_minor = ?,"
                 " selling_price_minor = COALESCE(?, selling_price_minor) WHERE batch_id = ?",
                 (purchase_price_minor, selling_price_minor, batch_id))


def change_quantity(conn, batch_id, delta):
    """Apply a guarded quantity change; returns rows updated (0 if it would go negative)."""
    return conn.execute(
        "UPDATE medicine_batches SET quantity_on_hand = quantity_on_hand + ?"
        " WHERE batch_id = ? AND quantity_on_hand + ? >= 0",
        (delta, batch_id, delta),
    ).rowcount


def batches(conn, medicine_id=None, in_stock_only=False, usable_from=None):
    sql = BATCH_SELECT + " WHERE 1 = 1"
    params: list = []
    if medicine_id:
        sql += " AND b.medicine_id = ?"
        params.append(medicine_id)
    if in_stock_only:
        sql += " AND b.quantity_on_hand > 0"
    if usable_from:
        sql += " AND b.expiry_date >= ?"
        params.append(usable_from)
    # FEFO order: earliest expiry first.
    return many(conn, sql + " ORDER BY b.expiry_date, b.batch_id", params)


def expiring_batches(conn, date_from, date_to):
    return many(conn, BATCH_SELECT + " WHERE b.quantity_on_hand > 0"
                " AND b.expiry_date BETWEEN ? AND ? ORDER BY b.expiry_date", (date_from, date_to))


def expired_batches(conn, today):
    return many(conn, BATCH_SELECT + " WHERE b.quantity_on_hand > 0 AND b.expiry_date < ?"
                " ORDER BY b.expiry_date", (today,))


def stock_by_category(conn, today):
    return many(conn, "SELECT COALESCE(m.category, 'Uncategorised') AS category,"
                      " SUM(b.quantity_on_hand) AS units FROM medicine_batches b"
                      " JOIN medicines m ON m.medicine_id = b.medicine_id"
                      " WHERE b.expiry_date >= ? AND b.quantity_on_hand > 0"
                      " GROUP BY category ORDER BY units DESC", (today,))


# --- movements -------------------------------------------------------------

def insert_movement(conn, batch_id, movement_type, delta, reason, reference, user_id):
    return conn.execute(
        "INSERT INTO stock_movements (batch_id, movement_type, quantity_delta, reason,"
        " reference, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (batch_id, movement_type, delta, reason, reference, user_id, clock.ts()),
    ).lastrowid


def movements(conn, date_from=None, date_to=None, medicine_id=None, movement_type=None,
              limit=2000):
    sql = ("SELECT sm.movement_id, sm.created_at, m.name AS medicine, b.batch_number,"
           " sm.movement_type, sm.quantity_delta, sm.reason, sm.reference, u.username"
           " FROM stock_movements sm JOIN medicine_batches b ON b.batch_id = sm.batch_id"
           " JOIN medicines m ON m.medicine_id = b.medicine_id"
           " LEFT JOIN users u ON u.user_id = sm.created_by WHERE 1 = 1")
    params: list = []
    if date_from:
        sql += " AND sm.created_at >= ?"
        params.append(f"{date_from} 00:00:00")
    if date_to:
        sql += " AND sm.created_at <= ?"
        params.append(f"{date_to} 23:59:59")
    if medicine_id:
        sql += " AND b.medicine_id = ?"
        params.append(medicine_id)
    if movement_type:
        sql += " AND sm.movement_type = ?"
        params.append(movement_type)
    sql += " ORDER BY sm.movement_id DESC LIMIT ?"
    params.append(limit)
    return many(conn, sql, params)


def issued_and_returned(conn, batch_id):
    row = conn.execute(
        "SELECT COALESCE(-SUM(CASE WHEN movement_type = 'ISSUE' THEN quantity_delta END), 0),"
        " COALESCE(SUM(CASE WHEN movement_type = 'RETURN' THEN quantity_delta END), 0)"
        " FROM stock_movements WHERE batch_id = ?", (batch_id,)).fetchone()
    return row[0], row[1]


def reconciliation_mismatches(conn):
    """Batches whose quantity differs from the sum of their movements."""
    return many(conn, "SELECT b.batch_id, b.batch_number, b.quantity_on_hand,"
                      " COALESCE(SUM(sm.quantity_delta), 0) AS movement_total"
                      " FROM medicine_batches b"
                      " LEFT JOIN stock_movements sm ON sm.batch_id = b.batch_id"
                      " GROUP BY b.batch_id HAVING b.quantity_on_hand != movement_total")


# --- suppliers & purchases -------------------------------------------------

def insert_supplier(conn, data):
    return conn.execute(
        f"INSERT INTO suppliers ({', '.join(SUPPLIER_FIELDS)})"
        f" VALUES ({', '.join('?' for _ in SUPPLIER_FIELDS)})",
        [data.get(f) for f in SUPPLIER_FIELDS],
    ).lastrowid


def update_supplier(conn, supplier_id, data):
    conn.execute(f"UPDATE suppliers SET {', '.join(f'{f} = ?' for f in SUPPLIER_FIELDS)}"
                 " WHERE supplier_id = ?", (*[data.get(f) for f in SUPPLIER_FIELDS], supplier_id))


def get_supplier(conn, supplier_id):
    return one(conn, "SELECT * FROM suppliers WHERE supplier_id = ?", (supplier_id,))


def list_suppliers(conn, active_only=False):
    sql = ("SELECT s.*, (SELECT COUNT(*) FROM purchases p WHERE p.supplier_id = s.supplier_id)"
           " AS purchases FROM suppliers s")
    if active_only:
        sql += " WHERE s.status = 'ACTIVE'"
    return many(conn, sql + " ORDER BY s.name")


def insert_purchase(conn, supplier_id, received_date, invoice_reference, user_id):
    return conn.execute(
        "INSERT INTO purchases (supplier_id, received_date, invoice_reference, created_by,"
        " created_at) VALUES (?, ?, ?, ?, ?)",
        (supplier_id, received_date, invoice_reference, user_id, clock.ts()),
    ).lastrowid


def insert_purchase_item(conn, purchase_id, batch_id, quantity, unit_cost_minor):
    conn.execute("INSERT INTO purchase_items (purchase_id, batch_id, quantity, unit_cost_minor)"
                 " VALUES (?, ?, ?, ?)", (purchase_id, batch_id, quantity, unit_cost_minor))


def purchases(conn, supplier_id=None, date_from=None, date_to=None):
    sql = ("SELECT p.purchase_id, p.received_date, s.name AS supplier, p.invoice_reference,"
           " m.name AS medicine, b.batch_number, b.expiry_date, pi.quantity,"
           " pi.unit_cost_minor, pi.quantity * pi.unit_cost_minor AS line_cost_minor"
           " FROM purchases p JOIN suppliers s ON s.supplier_id = p.supplier_id"
           " JOIN purchase_items pi ON pi.purchase_id = p.purchase_id"
           " JOIN medicine_batches b ON b.batch_id = pi.batch_id"
           " JOIN medicines m ON m.medicine_id = b.medicine_id WHERE 1 = 1")
    params: list = []
    if supplier_id:
        sql += " AND p.supplier_id = ?"
        params.append(supplier_id)
    if date_from:
        sql += " AND p.received_date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND p.received_date <= ?"
        params.append(date_to)
    return many(conn, sql + " ORDER BY p.received_date DESC, p.purchase_id DESC", params)


def count_medicines_in_stock(conn, today):
    return scalar(conn, "SELECT COUNT(DISTINCT medicine_id) FROM medicine_batches"
                        " WHERE quantity_on_hand > 0 AND expiry_date >= ?", (today,))
