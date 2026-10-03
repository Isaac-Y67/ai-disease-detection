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

# ---------- Heart disease model ----------
heart_model = joblib.load(os.path.join(SAVED_MODELS_DIR, "heart_disease_model.pkl"))
heart_scaler = joblib.load(os.path.join(SAVED_MODELS_DIR, "heart_disease_scaler.pkl"))

HEART_FEATURE_ORDER = [
    "age", "sex", "cp", "trestbps", "chol", "fbs", "restecg",
    "thalach", "exang", "oldpeak", "slope", "ca", "thal"
]

# ---------- Diabetes model ----------
diabetes_model = joblib.load(os.path.join(SAVED_MODELS_DIR, "diabetes_model.pkl"))
diabetes_scaler = joblib.load(os.path.join(SAVED_MODELS_DIR, "diabetes_scaler.pkl"))

DIABETES_FEATURE_ORDER = [
    "Pregnancies", "Glucose", "BloodPressure", "SkinThickness",
    "Insulin", "BMI", "DiabetesPedigreeFunction", "Age"
]


def classify_risk(prediction, probability):
    """Shared risk classification logic used by every disease module."""
    if prediction == 1:
        return "High" if probability >= 0.7 else "Moderate"
    return "Low"


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/diabetes")
def diabetes_page():
    return render_template("diabetes.html")


@app.route("/predict", methods=["POST"])
def predict_heart():
    data = request.get_json()

    try:
        features = [data[feature] for feature in HEART_FEATURE_ORDER]
    except KeyError as e:
        return jsonify({"error": f"Missing field: {e}"}), 400

    features_array = np.array(features).reshape(1, -1)
    features_scaled = heart_scaler.transform(features_array)

    prediction = heart_model.predict(features_scaled)[0]
    probability = heart_model.predict_proba(features_scaled)[0][1]
    risk_level = classify_risk(prediction, probability)

    return jsonify({
        "prediction": int(prediction),
        "disease_detected": bool(prediction == 1),
        "probability": round(float(probability), 4),
        "risk_level": risk_level
    })


@app.route("/predict-diabetes", methods=["POST"])
def predict_diabetes():
    data = request.get_json()

    try:
        features = [data[feature] for feature in DIABETES_FEATURE_ORDER]
    except KeyError as e:
        return jsonify({"error": f"Missing field: {e}"}), 400

    features_array = np.array(features).reshape(1, -1)
    features_scaled = diabetes_scaler.transform(features_array)

    prediction = diabetes_model.predict(features_scaled)[0]
    probability = diabetes_model.predict_proba(features_scaled)[0][1]
    risk_level = classify_risk(prediction, probability)

    return jsonify({
        "prediction": int(prediction),
        "disease_detected": bool(prediction == 1),
        "probability": round(float(probability), 4),
        "risk_level": risk_level
    })


if __name__ == "__main__":
    app.run(debug=True)