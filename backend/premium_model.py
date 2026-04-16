"""
Dynamic Premium Engine — ML-based actuarial pricing.

Upgraded for Phase 3:
  - Uses real city risk profiles (claim_rate, AQI baseline)
  - Gradient Boosting instead of Linear Regression for non-linear risk
  - Pool solvency factor: if reserve_ratio < 1.2, premium surcharge kicks in
  - Returns full breakdown for transparency (business viability)
"""

import os
import logging
import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor

logger = logging.getLogger("premium_model")

MODEL_PATH = os.path.join(os.path.dirname(__file__), "premium_model.pkl")


def _train_model() -> GradientBoostingRegressor:
    """
    Features: [avg_rainfall_mm, avg_temp_c, avg_aqi, claim_rate, pool_reserve_ratio]
    Target:   premium multiplier (1.0 = base price)
    """
    X = np.array([
        # rainfall, temp,  aqi,  claim_rate, reserve_ratio
        [80,  28,  150,  0.80, 1.0],   # High risk, stressed pool
        [60,  30,  200,  0.60, 1.2],
        [40,  32,  100,  0.40, 1.5],
        [20,  35,   80,  0.30, 2.0],
        [ 5,  38,   50,  0.10, 2.5],   # Low risk, healthy pool
        [90,  25,  180,  0.90, 0.8],   # Very high risk, underfunded pool
        [10,  36,   60,  0.20, 2.2],
        [50,  29,  120,  0.50, 1.3],
        [75,  27,  160,  0.75, 1.1],   # High risk
        [30,  33,   90,  0.35, 1.8],
        [15,  37,   70,  0.25, 2.0],
        [85,  24,  190,  0.85, 0.9],   # Extreme: underfunded + high risk
        [45,  31,  110,  0.45, 1.4],
        [65,  28,  145,  0.65, 1.15],
    ])
    y = np.array([1.80, 1.50, 1.20, 0.95, 0.75,
                  2.30, 0.80, 1.15, 1.70, 1.00,
                  0.85, 2.50, 1.10, 1.55])

    model = GradientBoostingRegressor(n_estimators=200, learning_rate=0.05, random_state=42)
    model.fit(X, y)
    joblib.dump(model, MODEL_PATH)
    logger.info("[Premium] Model trained and saved.")
    return model


if not os.path.exists(MODEL_PATH):
    _model = _train_model()
else:
    try:
        _model = joblib.load(MODEL_PATH)
    except Exception:
        logger.warning("[Premium] Corrupt model — retraining")
        _model = _train_model()


def calculate_dynamic_premium(
    base_premium: float,
    avg_rainfall: float,
    avg_temp: float,
    avg_aqi: float,
    claim_rate: float,
    pool_reserve_ratio: float = 1.5,
) -> dict:
    """
    Returns adjusted weekly premium with full actuarial breakdown.
    """
    features = np.array([[avg_rainfall, avg_temp, avg_aqi, claim_rate, pool_reserve_ratio]])
    raw_multiplier = float(_model.predict(features)[0])
    multiplier = round(max(0.5, min(3.0, raw_multiplier)), 2)

    # Pool solvency surcharge: if reserve_ratio < 1.2 we need extra buffer
    solvency_surcharge = 0.0
    if pool_reserve_ratio < 1.2:
        solvency_surcharge = round(base_premium * 0.15, 2)
        logger.info(f"[Premium] Pool reserve low ({pool_reserve_ratio:.2f}) — surcharge applied")

    adjusted = round(base_premium * multiplier + solvency_surcharge, 2)

    if multiplier > 1.6:
        risk_label, risk_color = "High Risk Zone",      "#EF4444"
    elif multiplier > 1.1:
        risk_label, risk_color = "Moderate Risk Zone",  "#F59E0B"
    else:
        risk_label, risk_color = "Low Risk Zone",       "#10B981"

    return {
        "base_premium":        base_premium,
        "multiplier":          multiplier,
        "adjusted_premium":    adjusted,
        "solvency_surcharge":  solvency_surcharge,
        "risk_label":          risk_label,
        "risk_color":          risk_color,
        "pool_reserve_ratio":  round(pool_reserve_ratio, 2),
        "savings":             round(base_premium - adjusted, 2) if adjusted < base_premium else 0,
        "extra_charge":        round(adjusted - base_premium, 2) if adjusted > base_premium else 0,
    }
