from flask import Flask, request, jsonify
import joblib
import numpy as np
import os

app = Flask(__name__)

# Build an absolute path based on THIS FILE's location, not the terminal's
# current directory — this makes it work no matter where you run it from
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "..", "..", "ml", "saved_models", "heart_disease_model.pkl")
SCALER_PATH = os.path.join(BASE_DIR, "..", "..", "ml", "saved_models", "heart_disease_scaler.pkl")

model = joblib.load(MODEL_PATH)
scaler = joblib.load(SCALER_PATH)

# The exact order of features the model was trained on
FEATURE_ORDER = [
    "age", "sex", "cp", "trestbps", "chol", "fbs", "restecg",
    "thalach", "exang", "oldpeak", "slope", "ca", "thal"
]

@app.route("/")
def home():
    return "AI Disease Detection System — backend is running."

@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json()

    try:
        features = [data[feature] for feature in FEATURE_ORDER]
    except KeyError as e:
        return jsonify({"error": f"Missing field: {e}"}), 400

    features_array = np.array(features).reshape(1, -1)
    features_scaled = scaler.transform(features_array)

    prediction = model.predict(features_scaled)[0]
    probability = model.predict_proba(features_scaled)[0][1]

    if prediction == 1:
        risk_level = "High" if probability >= 0.7 else "Moderate"
    else:
        risk_level = "Low"

    return jsonify({
        "prediction": int(prediction),
        "disease_detected": bool(prediction == 1),
        "probability": round(float(probability), 4),
        "risk_level": risk_level
    })

if __name__ == "__main__":
    app.run(debug=True)