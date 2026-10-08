from flask import Flask, request, jsonify, render_template
import joblib
import numpy as np
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "..", "..", "frontend", "templates"),
    static_folder=os.path.join(BASE_DIR, "..", "..", "frontend", "static")
)

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


# ---------- Pages ----------

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/diabetes")
def diabetes_page():
    return render_template("diabetes.html")


@app.route("/hypertension")
def hypertension_page():
    return render_template("hypertension.html")


# ---------- Prediction API ----------

@app.route("/predict", methods=["POST"])
def predict_heart():
    return run_prediction("heart")


@app.route("/predict-diabetes", methods=["POST"])
def predict_diabetes():
    return run_prediction("diabetes")


@app.route("/predict-hypertension", methods=["POST"])
def predict_hypertension():
    return run_prediction("hypertension")


if __name__ == "__main__":
    app.run(debug=True)