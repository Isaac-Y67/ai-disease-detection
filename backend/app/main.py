from datetime import timedelta
import os

from dotenv import load_dotenv
from flask import Flask, g, jsonify, redirect, render_template, request, session, url_for
import joblib
import numpy as np
import pymysql
from werkzeug.security import check_password_hash, generate_password_hash

import db
from auth import check_csrf, csrf_token, login_required, safe_next

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


def run_prediction(module_key):
    """One shared prediction pipeline for every disease module."""
    module = MODULES[module_key]
    data = request.get_json(silent=True)

    try:
        features = [data[name] for name in module["features"]]
    except (KeyError, TypeError) as e:
        return jsonify({"error": f"Missing field: {e}"}), 400

    features_array = np.array(features).reshape(1, -1)
    features_scaled = module["scaler"].transform(features_array)

    prediction = module["model"].predict(features_scaled)[0]
    probability = module["model"].predict_proba(features_scaled)[0][1]

    return jsonify({
        "prediction": int(prediction),
        "disease_detected": bool(prediction == 1),
        "probability": round(float(probability), 4),
        "risk_level": classify_risk(prediction, probability)
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
    return render_template("index.html")


@app.route("/diabetes")
@login_required
def diabetes_page():
    return render_template("diabetes.html")


@app.route("/hypertension")
@login_required
def hypertension_page():
    return render_template("hypertension.html")


@app.route("/lung-cancer")
@login_required
def lung_cancer_page():
    return render_template("lung_cancer.html")


# ---------- Prediction API (sign-in required) ----------

@app.route("/predict", methods=["POST"])
@login_required
def predict_heart():
    return run_prediction("heart")


@app.route("/predict-diabetes", methods=["POST"])
@login_required
def predict_diabetes():
    return run_prediction("diabetes")


@app.route("/predict-hypertension", methods=["POST"])
@login_required
def predict_hypertension():
    return run_prediction("hypertension")


@app.route("/predict-lung-cancer", methods=["POST"])
@login_required
def predict_lung_cancer():
    return run_prediction("lung_cancer")


if __name__ == "__main__":
    app.run(debug=True)
