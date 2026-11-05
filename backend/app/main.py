from datetime import date, timedelta
import math
import os
import re

from dotenv import load_dotenv
from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, session, url_for
import joblib
import numpy as np
import pymysql
from werkzeug.security import check_password_hash, generate_password_hash

import db
from validation import clean_patient_code, validate_features, PATIENT_CODE_PATTERN
from auth import ROLE_ADMIN, ROLE_HP, check_csrf, csrf_token, login_required, role_required, safe_next

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, "..", "..", ".env"))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "..", "..", "frontend", "templates"),
    static_folder=os.path.join(BASE_DIR, "..", "..", "frontend", "static")
)

# ---------- Security configuration (Section 5.6.2) ----------
app.secret_key = os.environ["SECRET_KEY"]
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,       # JavaScript can never read the session cookie
    SESSION_COOKIE_SAMESITE="Lax",      # the cookie is not sent on cross-site form posts
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "0") == "1",  # set to 1 behind HTTPS
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    MAX_CONTENT_LENGTH=64 * 1024,       # refuse oversized requests
)
app.jinja_env.globals["csrf_token"] = csrf_token

# A throw-away hash, so a login for an unknown email takes as long as a real one
DUMMY_HASH = generate_password_hash("not-a-real-password")

ACTION_LABELS = {
    "login": "Signed in",
    "login_failed": "Failed sign-in",
    "logout": "Signed out",
    "user_created": "Account created",
    "user_deactivated": "Account deactivated",
    "user_reactivated": "Account reactivated",
    "assessment_created": "Assessment saved",
    "assessment_viewed": "Record opened by an administrator",
    "password_changed": "Password changed",
    "password_change_failed": "Password change refused (wrong current password)",
}

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SAVED_MODELS_DIR = os.path.join(BASE_DIR, "..", "..", "ml", "saved_models")


def load_module(prefix, features):
    """Load a disease module's trained model and scaler, plus its feature order."""
    return {
        "model": joblib.load(os.path.join(SAVED_MODELS_DIR, f"{prefix}_model.pkl")),
        "scaler": joblib.load(os.path.join(SAVED_MODELS_DIR, f"{prefix}_scaler.pkl")),
        "features": features,
    }


# Each module's feature order MUST match the column order used during training.
MODULES = {
    "heart": load_module("heart_disease", [
        "age", "sex", "cp", "trestbps", "chol", "fbs", "restecg",
        "thalach", "exang", "oldpeak", "slope", "ca", "thal"
    ]),
    "diabetes": load_module("diabetes", [
        "Pregnancies", "Glucose", "BloodPressure", "SkinThickness",
        "Insulin", "BMI", "DiabetesPedigreeFunction", "Age"
    ]),
    "hypertension": load_module("hypertension", [
        "male", "age", "education", "currentSmoker", "cigsPerDay", "BPMeds",
        "prevalentStroke", "diabetes", "totChol", "sysBP", "diaBP",
        "BMI", "heartRate", "glucose"
    ]),
    "lung_cancer": load_module("lung_cancer", [
        "male", "age", "smoking", "yellow_fingers", "anxiety", "peer_pressure",
        "chronic_disease", "fatigue", "allergy", "wheezing", "alcohol_consuming",
        "coughing", "shortness_of_breath", "swallowing_difficulty", "chest_pain"
    ]),
}


def classify_risk(prediction, probability):
    """Shared risk classification used by every disease module."""
    if prediction == 1:
        return "High" if probability >= 0.7 else "Moderate"
    return "Low"


def patient_sex(module_key, data):
    """Sex for the patient record, taken from the form (the diabetes model was trained on women only)."""
    if module_key == "heart":
        return "Male" if data["sex"] == 1 else "Female"
    if module_key in ("hypertension", "lung_cancer"):
        return "Male" if data["male"] == 1 else "Female"
    return "Female"


def run_prediction(module_key):
    """One shared pipeline for every module: validate, predict, classify risk, save, answer."""
    module = MODULES[module_key]
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Send the assessment as JSON."}), 400

    patient_code = clean_patient_code(data.get("patient_code"))
    if patient_code is None:
        return jsonify({"error": "Enter a patient code of 1 to 20 letters, digits or hyphens. Do not use a name."}), 400

    values, problem = validate_features(module_key, data, module["features"])
    if problem:
        return jsonify({"error": problem}), 400

    features_array = np.array(values, dtype=float).reshape(1, -1)
    features_scaled = module["scaler"].transform(features_array)

    prediction = int(module["model"].predict(features_scaled)[0])
    probability = round(float(module["model"].predict_proba(features_scaled)[0][1]), 4)
    risk_level = classify_risk(prediction, probability)
    sex = patient_sex(module_key, data)

    try:
        assessment_id, _ = db.save_assessment(
            g.user["user_id"], patient_code, sex, module_key,
            dict(zip(module["features"], values)), prediction, probability, risk_level)
    except db.PatientConflict as conflict:
        return jsonify({"error": f"Patient code {patient_code} is already registered as "
                                 f"{conflict.existing_sex}, but this form says {sex}. Check the code."}), 409

    db.write_audit(g.user["user_id"], "assessment_created", "assessments", assessment_id, request.remote_addr)

    return jsonify({
        "prediction": prediction,
        "disease_detected": prediction == 1,
        "probability": probability,
        "risk_level": risk_level,
        "assessment_id": assessment_id,
        "patient_code": patient_code,
    })


# ---------- Who is signed in? (runs before every request) ----------

@app.before_request
def load_current_user():
    g.user = None
    if request.endpoint == "static":
        return
    user_id = session.get("user_id")
    if user_id is None:
        return
    user = db.get_user_by_id(user_id)
    if user is None or not user["is_active"]:   # a deactivated account loses access immediately
        session.clear()
        return
    g.user = user


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    if g.get("user") is not None:
        response.headers["Cache-Control"] = "no-store"   # the Back button cannot reveal pages after sign-out
    return response


@app.errorhandler(pymysql.MySQLError)
def database_unavailable(err):
    app.logger.error("Database error: %s", err)
    if request.path.startswith("/predict"):
        return jsonify({"error": "The database is temporarily unavailable"}), 503
    return "The database is temporarily unavailable. Please try again shortly.", 503


def error_page(code, title, message):
    return render_template("error.html", code=code, title=title, message=message), code


@app.errorhandler(400)
def bad_request(err):
    return error_page(400, "Request not accepted", err.description)


@app.errorhandler(403)
def forbidden(err):
    if request.path.startswith("/predict") or request.path.startswith("/api/"):
        return jsonify({"error": "Your role is not allowed to do this"}), 403
    return error_page(403, "Not allowed", "Your role does not have access to this page.")


@app.errorhandler(404)
def not_found(err):
    return error_page(404, "Page not found", "That page does not exist.")


# ---------- Sign in and out ----------

@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user is not None:
        return redirect(url_for("home"))

    next_url = safe_next(request.values.get("next"))
    error = None

    if request.method == "POST":
        check_csrf()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = db.get_user_by_email(email) if email else None

        # Always check one hash, so the response time does not reveal whether the email exists
        password_ok = check_password_hash(user["password_hash"] if user else DUMMY_HASH, password)

        if user and user["is_active"] and password_ok:
            session.clear()
            session["user_id"] = user["user_id"]
            session.permanent = True
            db.write_audit(user["user_id"], "login", "users", user["user_id"], request.remote_addr)
            return redirect(next_url or url_for("home"))

        db.write_audit(user["user_id"] if user else None, "login_failed", "users",
                       user["user_id"] if user else None, request.remote_addr)
        error = "Invalid email or password."   # the same message for every kind of failure

    return render_template("login.html", error=error, next_url=next_url or "",
                           email=request.form.get("email", ""))


@app.route("/logout", methods=["POST"])
def logout():
    check_csrf()
    if g.user is not None:
        db.write_audit(g.user["user_id"], "logout", "users", g.user["user_id"], request.remote_addr)
    session.clear()
    return redirect(url_for("login"))


# ---------- Pages (sign-in required) ----------

@app.route("/")
@login_required
def home():
    if g.user["role_name"] == ROLE_ADMIN:      # administrators manage the system, they do not run assessments
        return redirect(url_for("admin_users"))
    return render_template("index.html")


@app.route("/diabetes")
@role_required(ROLE_HP)
def diabetes_page():
    return render_template("diabetes.html")


@app.route("/hypertension")
@role_required(ROLE_HP)
def hypertension_page():
    return render_template("hypertension.html")


@app.route("/lung-cancer")
@role_required(ROLE_HP)
def lung_cancer_page():
    return render_template("lung_cancer.html")


# ---------- Prediction API (sign-in required) ----------

@app.route("/predict", methods=["POST"])
@role_required(ROLE_HP)
def predict_heart():
    return run_prediction("heart")


@app.route("/predict-diabetes", methods=["POST"])
@role_required(ROLE_HP)
def predict_diabetes():
    return run_prediction("diabetes")


@app.route("/predict-hypertension", methods=["POST"])
@role_required(ROLE_HP)
def predict_hypertension():
    return run_prediction("hypertension")


@app.route("/predict-lung-cancer", methods=["POST"])
@role_required(ROLE_HP)
def predict_lung_cancer():
    return run_prediction("lung_cancer")


# ---------- Assessment lists (shared filter handling) ----------

PAGE_SIZE = 20
AUDIT_PAGE_SIZE = 50


def parse_date(text):
    try:
        return date.fromisoformat(text) if text else None
    except ValueError:
        return None


def read_page():
    try:
        return max(1, int(request.args.get("page", "1")))
    except ValueError:
        return 1


def read_assessment_filters(modules):
    """Read the filter box. Anything that is not valid is quietly ignored, never passed to the database."""
    patient = request.args.get("patient", "").strip().upper()
    if patient and not PATIENT_CODE_PATTERN.match(patient):
        patient = ""
    module = request.args.get("module", "")
    if module not in [m["module_code"] for m in modules]:
        module = ""
    return patient, module, parse_date(request.args.get("from")), parse_date(request.args.get("to"))


def build_filters(**values):
    """The filters that must survive on the Previous / Next links (empty ones are dropped)."""
    names = {"date_from": "from", "date_to": "to"}
    cleaned = {}
    for key, value in values.items():
        if isinstance(value, date):
            value = value.isoformat()
        if value:
            cleaned[names.get(key, key)] = value
    return cleaned


@app.route("/history")
@role_required(ROLE_HP)
def history():
    modules = db.list_modules()
    patient, module, date_from, date_to = read_assessment_filters(modules)
    page = read_page()
    rows, total = db.search_assessments(
        user_id=g.user["user_id"], patient_code=patient, module_code=module,
        date_from=date_from, date_to=date_to, limit=PAGE_SIZE, offset=(page - 1) * PAGE_SIZE)
    filters = build_filters(patient=patient, module=module, date_from=date_from, date_to=date_to)
    return render_template("history.html", rows=rows, total=total, page=page,
                           pages=max(1, math.ceil(total / PAGE_SIZE)), modules=modules, filters=filters,
                           patient=patient, module=module,
                           date_from=filters.get("from", ""), date_to=filters.get("to", ""))


@app.route("/assessment/<int:assessment_id>")
@login_required
def assessment_detail(assessment_id):
    is_admin = g.user["role_name"] == ROLE_ADMIN
    # A healthcare professional can open only their own records; an administrator can open any (Table 20)
    assessment = db.get_assessment(assessment_id, user_id=None if is_admin else g.user["user_id"])
    if assessment is None:
        abort(404)
    if is_admin:   # opening a patient record is itself recorded
        db.write_audit(g.user["user_id"], "assessment_viewed", "assessments", assessment_id, request.remote_addr)
    return render_template("assessment_detail.html", a=assessment, active_page="assessments")


# ---------- Account: change your own password ----------

@app.route("/account/password", methods=["GET", "POST"])
@login_required
def change_password():
    problem = None
    if request.method == "POST":
        check_csrf()
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        user = db.get_user_by_id(g.user["user_id"])     # read the stored hash fresh

        if not check_password_hash(user["password_hash"], current):
            problem = "Your current password is not correct."
            db.write_audit(user["user_id"], "password_change_failed", "users", user["user_id"], request.remote_addr)
        elif len(new) < 10 or len(new) > 256:
            problem = "The new password must be between 10 and 256 characters."
        elif new != confirm:
            problem = "The two new passwords do not match."
        elif new == current:
            problem = "Choose a password that is different from the current one."

        if problem is None:
            db.update_password(user["user_id"], generate_password_hash(new))
            db.write_audit(user["user_id"], "password_changed", "users", user["user_id"], request.remote_addr)
            session.clear()                       # a fresh session after any change of credentials
            session["user_id"] = user["user_id"]
            session.permanent = True
            flash("Your password was changed.", "ok")
            return redirect(url_for("change_password"))

    return render_template("account_password.html", active_page="account", problem=problem), (400 if problem else 200)


# ---------- Administration (administrators only) ----------

@app.route("/admin/assessments")
@role_required(ROLE_ADMIN)
def admin_assessments():
    modules, staff = db.list_modules(), db.list_users()
    patient, module, date_from, date_to = read_assessment_filters(modules)
    staff_ids = {str(u["user_id"]): u["user_id"] for u in staff}
    staff_id = staff_ids.get(request.args.get("staff", ""))
    page = read_page()
    rows, total = db.search_assessments(
        user_id=staff_id, patient_code=patient, module_code=module,
        date_from=date_from, date_to=date_to, limit=PAGE_SIZE, offset=(page - 1) * PAGE_SIZE)
    filters = build_filters(patient=patient, module=module, date_from=date_from, date_to=date_to,
                            staff=str(staff_id) if staff_id else "")
    return render_template("admin_assessments.html", active_page="assessments", rows=rows, total=total,
                           page=page, pages=max(1, math.ceil(total / PAGE_SIZE)), modules=modules, staff=staff,
                           filters=filters, patient=patient, module=module, staff_id=str(staff_id or ""),
                           date_from=filters.get("from", ""), date_to=filters.get("to", ""))


@app.route("/admin/audit")
@role_required(ROLE_ADMIN)
def admin_audit():
    actions = db.list_audit_actions()
    action = request.args.get("action", "")
    if action not in actions:
        action = ""
    date_from, date_to = parse_date(request.args.get("from")), parse_date(request.args.get("to"))
    page = read_page()
    rows, total = db.search_audit(action=action, date_from=date_from, date_to=date_to,
                                  limit=AUDIT_PAGE_SIZE, offset=(page - 1) * AUDIT_PAGE_SIZE)
    filters = build_filters(action=action, date_from=date_from, date_to=date_to)
    return render_template("admin_audit.html", active_page="audit", rows=rows, total=total, page=page,
                           pages=max(1, math.ceil(total / AUDIT_PAGE_SIZE)), actions=actions, labels=ACTION_LABELS,
                           filters=filters, action=action,
                           date_from=filters.get("from", ""), date_to=filters.get("to", ""))


def render_users_page(problem=None, form=None, status=200):
    return render_template("admin_users.html", active_page="users", users=db.list_users(),
                           roles=db.list_roles(), problem=problem, form=form or {}), status


@app.route("/admin/users", methods=["GET", "POST"])
@role_required(ROLE_ADMIN)
def admin_users():
    if request.method == "GET":
        return render_users_page()

    check_csrf()
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    role_name = request.form.get("role", "")
    password = request.form.get("password", "")

    problem = None
    if not full_name or len(full_name) > 100:
        problem = "Enter the person's full name (up to 100 characters)."
    elif len(email) > 120 or not EMAIL_PATTERN.match(email):
        problem = "Enter a valid email address."
    elif role_name not in db.list_roles():
        problem = "Choose a role from the list."
    elif len(password) < 10 or len(password) > 256:
        problem = "The password must be at least 10 characters (up to 256)."

    if problem is None:
        new_id = db.create_user(full_name, email, generate_password_hash(password), role_name)
        if new_id is None:
            problem = "An account with that email already exists."
        else:
            db.write_audit(g.user["user_id"], "user_created", "users", new_id, request.remote_addr)
            flash(f"Account created for {email} ({role_name}).", "ok")
            return redirect(url_for("admin_users"))

    # Keep what was typed (never the password) so the form does not have to be refilled
    return render_users_page(problem=problem, form={"full_name": full_name, "email": email, "role": role_name}, status=400)


@app.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
@role_required(ROLE_ADMIN)
def admin_toggle_user(user_id):
    check_csrf()
    if user_id == g.user["user_id"]:
        # Because an administrator can never deactivate themselves, at least one active administrator always remains
        flash("You cannot deactivate your own account.", "error")
        return redirect(url_for("admin_users"))
    target = db.get_user_by_id(user_id)
    if target is None:
        abort(404)
    make_active = not target["is_active"]
    db.set_user_active(user_id, make_active)
    db.write_audit(g.user["user_id"], "user_reactivated" if make_active else "user_deactivated",
                   "users", user_id, request.remote_addr)
    flash(f"{target['email']} is now {'active' if make_active else 'deactivated'}.", "ok")
    return redirect(url_for("admin_users"))


if __name__ == "__main__":
    app.run(debug=True)
