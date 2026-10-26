"""Repository layer: every database query of the application lives in this file (Figure 10).

All values travel as query parameters (%s) and are never pasted into the SQL text.
This is the defence against SQL injection described in Section 5.6.2.
"""
import os

import pymysql


def get_connection():
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        cursorclass=pymysql.cursors.DictCursor,
        charset="utf8mb4",
        connect_timeout=5,
    )


def get_user_by_email(email):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT u.user_id, u.full_name, u.email, u.password_hash, u.is_active, r.role_name "
                "FROM users u JOIN roles r ON r.role_id = u.role_id WHERE u.email = %s",
                (email,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT u.user_id, u.full_name, u.email, u.password_hash, u.is_active, r.role_name "
                "FROM users u JOIN roles r ON r.role_id = u.role_id WHERE u.user_id = %s",
                (user_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def write_audit(user_id, action, entity=None, entity_id=None, ip_address=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO audit_log (user_id, action, entity, entity_id, ip_address) "
                "VALUES (%s, %s, %s, %s, %s)",
                (user_id, action, entity, entity_id, ip_address),
            )
        conn.commit()
    finally:
        conn.close()


# ---------- User management (administrator pages) ----------

def list_roles():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT role_name FROM roles ORDER BY role_id")
            return [row["role_name"] for row in cur.fetchall()]
    finally:
        conn.close()


def list_users():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT u.user_id, u.full_name, u.email, u.is_active, u.created_at, r.role_name "
                "FROM users u JOIN roles r ON r.role_id = u.role_id ORDER BY u.user_id"
            )
            return cur.fetchall()
    finally:
        conn.close()


def create_user(full_name, email, password_hash, role_name):
    """Insert a user. Returns the new user_id, or None if the email is already registered."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT role_id FROM roles WHERE role_name = %s", (role_name,))
            role = cur.fetchone()
            if role is None:
                raise ValueError("Unknown role")
            try:
                cur.execute(
                    "INSERT INTO users (full_name, email, password_hash, role_id) VALUES (%s, %s, %s, %s)",
                    (full_name, email, password_hash, role["role_id"]),
                )
            except pymysql.err.IntegrityError:
                conn.rollback()
                return None
            new_id = cur.lastrowid
        conn.commit()
        return new_id
    finally:
        conn.close()


def set_user_active(user_id, is_active):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET is_active = %s WHERE user_id = %s", (int(is_active), user_id))
            changed = cur.rowcount
        conn.commit()
        return changed
    finally:
        conn.close()
