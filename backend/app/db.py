"""Repository layer: every database query of the application lives in this file (Figure 10).

All values travel as query parameters (%s) and are never pasted into the SQL text.
This is the defence against SQL injection described in Section 5.6.2.
"""
import json
import os
from datetime import timedelta

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


# ---------- Assessments ----------

class PatientConflict(Exception):
    """The patient code already exists but belongs to a patient of the other sex (probably a mistyped code)."""
    def __init__(self, existing_sex):
        super().__init__(existing_sex)
        self.existing_sex = existing_sex


def list_modules():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT module_code, module_name FROM disease_modules ORDER BY module_id")
            return cur.fetchall()
    finally:
        conn.close()


def save_assessment(user_id, patient_code, sex, module_code, features, prediction, probability, risk_level):
    """Store one prediction with its inputs and the model version that produced it.

    The patient is created on first use. Returns (assessment_id, patient_is_new).
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT mv.model_version_id FROM model_versions mv "
                "JOIN disease_modules m ON m.module_id = mv.module_id "
                "WHERE m.module_code = %s AND mv.is_active = 1 "
                "ORDER BY mv.model_version_id DESC LIMIT 1",
                (module_code,),
            )
            model = cur.fetchone()
            if model is None:
                raise LookupError("No active model version is registered for this module")

            cur.execute("SELECT patient_id, sex FROM patients WHERE patient_code = %s", (patient_code,))
            patient = cur.fetchone()
            is_new = patient is None
            if is_new:
                cur.execute(
                    "INSERT INTO patients (patient_code, sex, registered_by) VALUES (%s, %s, %s)",
                    (patient_code, sex, user_id),
                )
                patient_id = cur.lastrowid
            else:
                if patient["sex"] != sex:
                    raise PatientConflict(patient["sex"])
                patient_id = patient["patient_id"]

            cur.execute(
                "INSERT INTO assessments (patient_id, model_version_id, performed_by, input_data, "
                "prediction, probability, risk_level) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (patient_id, model["model_version_id"], user_id, json.dumps(features),
                 int(prediction), float(probability), risk_level),
            )
            assessment_id = cur.lastrowid
        conn.commit()
        return assessment_id, is_new
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def search_assessments(user_id=None, patient_code=None, module_code=None,
                       date_from=None, date_to=None, limit=20, offset=0):
    """List assessments newest first. Every filter is optional. Returns (rows, total_count)."""
    conditions, params = [], []
    if user_id is not None:
        conditions.append("a.performed_by = %s")
        params.append(user_id)
    if patient_code:
        conditions.append("p.patient_code LIKE %s")
        params.append(patient_code + "%")          # the code is validated to letters, digits and hyphens first
    if module_code:
        conditions.append("m.module_code = %s")
        params.append(module_code)
    if date_from:
        conditions.append("a.created_at >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("a.created_at < %s")
        params.append(date_to + timedelta(days=1))  # the end date is inclusive
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    source = (
        " FROM assessments a JOIN patients p ON p.patient_id = a.patient_id"
        " JOIN model_versions mv ON mv.model_version_id = a.model_version_id"
        " JOIN disease_modules m ON m.module_id = mv.module_id" + where
    )
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n" + source, params)
            total = cur.fetchone()["n"]
            cur.execute(
                "SELECT a.assessment_id, a.created_at, p.patient_code, m.module_code, m.module_name, "
                "a.prediction, a.probability, a.risk_level, mv.algorithm" + source +
                " ORDER BY a.created_at DESC, a.assessment_id DESC LIMIT %s OFFSET %s",
                params + [limit, offset],
            )
            rows = cur.fetchall()
        for row in rows:
            row["probability"] = float(row["probability"])
        return rows, total
    finally:
        conn.close()


def get_assessment(assessment_id, user_id=None):
    """One assessment with its inputs and model details. With user_id, only that user's own assessment."""
    sql = (
        "SELECT a.assessment_id, a.created_at, a.input_data, a.prediction, a.probability, a.risk_level, "
        "p.patient_code, p.sex, m.module_code, m.module_name, mv.model_version_id, mv.algorithm, "
        "mv.trained_on, u.full_name AS performed_by_name "
        "FROM assessments a JOIN patients p ON p.patient_id = a.patient_id "
        "JOIN model_versions mv ON mv.model_version_id = a.model_version_id "
        "JOIN disease_modules m ON m.module_id = mv.module_id "
        "JOIN users u ON u.user_id = a.performed_by WHERE a.assessment_id = %s"
    )
    params = [assessment_id]
    if user_id is not None:
        sql += " AND a.performed_by = %s"
        params.append(user_id)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        if row is None:
            return None
        row["probability"] = float(row["probability"])
        if isinstance(row["input_data"], (str, bytes)):
            row["input_data"] = json.loads(row["input_data"])
        return row
    finally:
        conn.close()
