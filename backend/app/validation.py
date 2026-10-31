"""Server-side validation of assessment inputs (Section 5.6.2: presence and numeric range).

Every value must be a real number, a whole number where the field is a code, and inside a
plausible clinical range. Rejecting nonsense here keeps it out of the model and out of the database.
"""
import math
import re

PATIENT_CODE_PATTERN = re.compile(r"^[A-Z0-9-]{1,20}$")

BIN = (0, 1, True)   # a yes/no answer: 0 or 1

# feature: (minimum, maximum, whole numbers only?)
RULES = {
    "heart": {
        "age": (1, 120, True), "sex": BIN, "cp": (0, 3, True), "trestbps": (50, 300, False),
        "chol": (50, 700, False), "fbs": BIN, "restecg": (0, 2, True), "thalach": (40, 250, False),
        "exang": BIN, "oldpeak": (0, 10, False), "slope": (0, 2, True), "ca": (0, 4, True), "thal": (0, 3, True),
    },
    "diabetes": {
        "Pregnancies": (0, 20, True), "Glucose": (20, 600, False), "BloodPressure": (20, 200, False),
        "SkinThickness": (1, 100, False), "Insulin": (1, 900, False), "BMI": (10, 80, False),
        "DiabetesPedigreeFunction": (0, 5, False), "Age": (1, 120, True),
    },
    "hypertension": {
        "male": BIN, "age": (1, 120, True), "education": (1, 4, True), "currentSmoker": BIN,
        "cigsPerDay": (0, 100, True), "BPMeds": BIN, "prevalentStroke": BIN, "diabetes": BIN,
        "totChol": (50, 700, False), "sysBP": (60, 300, False), "diaBP": (30, 200, False),
        "BMI": (10, 80, False), "heartRate": (30, 220, False), "glucose": (30, 600, False),
    },
    "lung_cancer": {
        "male": BIN, "age": (1, 120, True), "smoking": BIN, "yellow_fingers": BIN, "anxiety": BIN,
        "peer_pressure": BIN, "chronic_disease": BIN, "fatigue": BIN, "allergy": BIN, "wheezing": BIN,
        "alcohol_consuming": BIN, "coughing": BIN, "shortness_of_breath": BIN,
        "swallowing_difficulty": BIN, "chest_pain": BIN,
    },
}


def clean_patient_code(value):
    """Upper-case and check a patient code. Returns None if it is not a valid code."""
    code = str(value or "").strip().upper()
    return code if PATIENT_CODE_PATTERN.match(code) else None


def validate_features(module_key, data, features):
    """Check every input. Returns (values_in_model_order, None) or (None, error_message)."""
    rules = RULES[module_key]
    values = []
    for name in features:
        if name not in data:
            return None, f"Missing field: '{name}'"
        v = data[name]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            return None, f"'{name}' must be a number."
        low, high, whole = rules[name]
        if whole and v != int(v):
            return None, f"'{name}' must be a whole number."
        if not (low <= v <= high):
            return None, f"'{name}' must be between {low} and {high}."
        values.append(v)
    return values, None
