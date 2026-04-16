"""
Policy Routes — plan info, dynamic premium, my policy
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from database import get_db
from models import Worker, InsurancePolicy, PremiumPool
from constants import INSURANCE_PLANS, CITY_CENTERS
from weather_service import get_weather
from premium_model import calculate_dynamic_premium
from security import get_current_user

logger = logging.getLogger("policy_routes")

router = APIRouter(prefix="/api/policy", tags=["policy"])


@router.get("/plans")
def get_plans():
    """Returns all available plans."""
    return INSURANCE_PLANS


@router.get("/my-policy")
def get_my_policy(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    worker = get_current_user(authorization, db)
    policy = db.query(InsurancePolicy).filter(
        InsurancePolicy.worker_id == worker.id,
        InsurancePolicy.is_active == True,
    ).first()

    if not policy:
        return {"has_policy": False, "message": "No active policy"}

    return {
        "has_policy":    True,
        "plan_type":     policy.plan_type,
        "weekly_premium": policy.weekly_premium,
        "max_payout":    policy.max_payout,
        "rain_threshold": policy.rain_threshold,
        "heat_threshold": policy.heat_threshold,
        "aqi_threshold": policy.aqi_threshold,
        "civil_coverage": policy.civil_coverage,
        "is_active":     policy.is_active,
    }


@router.get("/dynamic-premium/{plan_type}")
def get_dynamic_premium(
    plan_type: str,
    city: str = "Mumbai",
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """ML-based dynamic premium: adjusts price based on real-time city risk + pool solvency."""
    if plan_type not in INSURANCE_PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan type")

    base_premium = INSURANCE_PLANS[plan_type]["weekly_premium"]
    weather      = get_weather(city)
    city_info    = CITY_CENTERS.get(city, {"aqi_baseline": 120, "claim_rate": 0.5})

    # Get pool reserve ratio for this city
    pool = db.query(PremiumPool).filter(PremiumPool.city == city).first()
    reserve_ratio = pool.reserve_ratio if pool else 1.5

    result = calculate_dynamic_premium(
        base_premium       = base_premium,
        avg_rainfall       = weather["rainfall"],
        avg_temp           = weather["temperature"],
        avg_aqi            = city_info["aqi_baseline"],
        claim_rate         = city_info["claim_rate"],
        pool_reserve_ratio = reserve_ratio,
    )

    return {"city": city, "plan": plan_type, **result}
