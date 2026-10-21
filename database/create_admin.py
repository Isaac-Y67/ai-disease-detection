"""Create the first administrator account.

Run once from the project folder:   winpty python database/create_admin.py
The password is typed at a hidden prompt, hashed with a salt, and only the hash is stored.
"""
import getpass
import os
import re
import sys

import pymysql
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def connect():
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
    )


def ask_details():
    full_name = input("Full name: ").strip()
    email = input("Email: ").strip().lower()
    if not full_name or not EMAIL_PATTERN.match(email):
        sys.exit("A full name and a valid email address are required. Nothing was saved.")
    password = getpass.getpass("Password (hidden, at least 10 characters): ")
    if len(password) < 10:
        sys.exit("The password must be at least 10 characters. Nothing was saved.")
    if getpass.getpass("Repeat password: ") != password:
        sys.exit("The two passwords did not match. Nothing was saved.")
    return full_name, email, password


def main():
    full_name, email, password = ask_details()
    password_hash = generate_password_hash(password)  # salted hash; the plain password is never stored

    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT role_id FROM roles WHERE role_name = %s", ("Administrator",))
            role = cur.fetchone()
            if role is None:
                sys.exit("The Administrator role was not found. Was schema.sql loaded?")
            try:
                cur.execute(
                    "INSERT INTO users (full_name, email, password_hash, role_id) VALUES (%s, %s, %s, %s)",
                    (full_name, email, password_hash, role[0]),
                )
            except pymysql.err.IntegrityError:
                sys.exit("An account with that email already exists. Nothing was saved.")
            user_id = cur.lastrowid
            cur.execute(
                "INSERT INTO audit_log (user_id, action, entity, entity_id) VALUES (%s, %s, %s, %s)",
                (user_id, "user_created", "users", user_id),
            )
        conn.commit()
    finally:
        conn.close()
    print(f"Administrator created: id {user_id}, {email}")


if __name__ == "__main__":
    main()
