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
