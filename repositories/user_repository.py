from repositories.common import many, one, scalar
from utils import clock

PUBLIC_COLUMNS = ("u.user_id, u.username, u.full_name, u.role, u.staff_id, u.active,"
                  " u.created_at, u.last_login_at")


def get_by_username(conn, username):
    return one(conn, "SELECT * FROM users WHERE username = ?", (username,))


def get(conn, user_id):
    return one(conn, f"SELECT {PUBLIC_COLUMNS} FROM users u WHERE u.user_id = ?", (user_id,))


def list_all(conn):
    return many(conn, f"SELECT {PUBLIC_COLUMNS}, s.full_name AS staff_name FROM users u"
                      " LEFT JOIN staff s ON s.staff_id = u.staff_id ORDER BY u.username")


def count(conn):
    return scalar(conn, "SELECT COUNT(*) FROM users")


def count_active_admins(conn):
    return scalar(conn, "SELECT COUNT(*) FROM users WHERE role = 'ADMIN' AND active = 1")


def insert(conn, username, full_name, password_hash, role, staff_id):
    cur = conn.execute(
        "INSERT INTO users (username, full_name, password_hash, role, staff_id, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (username, full_name, password_hash, role, staff_id, clock.ts()),
    )
    return cur.lastrowid


def update(conn, user_id, full_name, role, staff_id, active):
    conn.execute(
        "UPDATE users SET full_name = ?, role = ?, staff_id = ?, active = ? WHERE user_id = ?",
        (full_name, role, staff_id, int(active), user_id),
    )


def set_password(conn, user_id, password_hash):
    conn.execute("UPDATE users SET password_hash = ? WHERE user_id = ?",
                 (password_hash, user_id))


def touch_login(conn, user_id):
    conn.execute("UPDATE users SET last_login_at = ? WHERE user_id = ?",
                 (clock.ts(), user_id))
