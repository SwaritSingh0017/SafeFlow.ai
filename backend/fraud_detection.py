"""
Fraud Detection Engine — Isolation Forest + rule-based override.

Upgraded features vs. Phase 2:
  - More training data points covering edge cases
  - Velocity check: claims per day (not just total count)
  - Account age weighted risk
  - Rule-based hard overrides (new account + multiple claims = automatic flag)
"""

import os
import logging
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

logger = logging.getLogger("fraud_detection")

MODEL_PATH = os.path.join(os.path.dirname(__file__), "fraud_model.pkl")


def _train_model() -> IsolationForest:
    """
    Train Isolation Forest on labelled behaviour patterns.
    Features: [rainfall_mm, temperature_c, claims_count, account_age_days, claims_per_day]
    """
    # (rainfall, temp, claims_count, account_age_days, claims_per_day)
    # Legitimate patterns — realistic weather events, experienced workers
    legitimate = [
        [80, 25, 1, 200, 0.005],
        [70, 26, 2, 150, 0.013],
        [90, 24, 1, 180, 0.006],
        [55, 28, 3, 365, 0.008],
        [65, 27, 2, 300, 0.007],
        [40, 30, 1, 120, 0.008],
        [85, 23, 1, 400, 0.003],
        [30, 40, 2, 250, 0.008],
        [20, 42, 1, 90,  0.011],
        [95, 22, 2, 500, 0.004],
        [50, 29, 3, 200, 0.015],
        [60, 27, 1, 600, 0.002],
    ]
    # Fraudulent patterns — no weather + many claims, new accounts, high velocity
    fraudulent = [
        [0,  35, 5,  3,   1.667],
        [0,  34, 6,  2,   3.000],
        [2,  33, 8,  5,   1.600],
        [1,  36, 4,  7,   0.571],
        [3,  37, 7,  4,   1.750],
        [0,  38, 9,  1,   9.000],
        [5,  35, 5,  10,  0.500],
        [0,  36, 3,  2,   1.500],
    ]

    X = np.array(legitimate + fraudulent)
    # IsolationForest: contamination = fraction of fraudulent in training set
    model = IsolationForest(
        n_estimators=200,
        contamination=len(fraudulent) / len(X),
        random_state=42
    )
    model.fit(X)
    joblib.dump(model, MODEL_PATH)
    logger.info("[Fraud] Model trained and saved.")
    return model


# Load or train at import time
if not os.path.exists(MODEL_PATH):
    _model = _train_model()
else:
    try:
        _model = joblib.load(MODEL_PATH)
    except Exception:
        logger.warning("[Fraud] Corrupt model file — retraining")
        _model = _train_model()


def predict_fraud(
    rainfall: float,
    temperature: float,
    claims_count: int,
    account_age_days: int,
    claims_per_day: float = None,
) -> dict:
    """
    Returns {"is_fraud": bool, "confidence": float, "reason": str}

    Hard rules take priority over ML model:
      - Account < 3 days AND claims > 1  → fraud
      - claims_per_day > 2.0             → fraud (velocity spike)
      - rainfall < 1mm AND claims > 2    → suspicious (no weather basis)
    """
    # Defensive defaults
    account_age_days = max(account_age_days, 1)
    if claims_per_day is None:
        claims_per_day = claims_count / account_age_days

    # --- Hard rule overrides ---
    if account_age_days < 3 and claims_count > 1:
        return {"is_fraud": True, "confidence": 0.98, "reason": "New account with multiple claims"}

    if claims_per_day > 2.0:
        return {"is_fraud": True, "confidence": 0.95, "reason": f"Velocity spike: {claims_per_day:.1f} claims/day"}

    if rainfall < 1.0 and temperature < 38 and claims_count > 2:
        return {"is_fraud": True, "confidence": 0.80, "reason": "Claims with no weather trigger basis"}

    # --- ML model ---
    features = np.array([[rainfall, temperature, claims_count, account_age_days, claims_per_day]])
    score = float(_model.decision_function(features)[0])
    prediction = _model.predict(features)[0]  # -1 = anomaly, 1 = normal

    # Convert raw score to a 0-1 confidence (higher = more fraudulent)
    # decision_function: negative = anomaly, positive = normal
    confidence = round(max(0.0, min(1.0, -score / 0.3 + 0.5)), 2)

    if prediction == -1:
        return {"is_fraud": True,  "confidence": confidence, "reason": "ML anomaly detected"}
    return     {"is_fraud": False, "confidence": confidence, "reason": "Behaviour within normal range"}
