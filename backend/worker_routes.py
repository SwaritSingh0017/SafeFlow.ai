"""
Worker Routes — weather, risk, wallet, claims, parametric trigger, community
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Worker, Claim, InsurancePolicy, CommunityPost, PremiumPool
from weather_service import get_weather
from fraud_detection import predict_fraud
from constants import CITY_CENTERS, GPS_BOUNDARY_THRESHOLD, INSURANCE_PLANS
from security import get_current_user, utcnow

logger = logging.getLogger("worker_routes")

router = APIRouter(prefix="/api", tags=["worker"])


# ─── Weather & Risk ───────────────────────────────────────────────────────────

@router.get("/weather")
def weather_endpoint(city: str):
    data = get_weather(city)
    return {
        "city":         data["city"],
        "temp_celsius": data["temperature"],
        "rain_mm":      data["rainfall"],
        "wind_kmh":     data["wind"],
        "humidity":     data["humidity"],
        "aqi":          data["aqi"],
        "summary":      _weather_summary(data),
    }


@router.get("/risk")
def risk_endpoint(city: str):
    data = get_weather(city)
    city_info = CITY_CENTERS.get(city, {"aqi_baseline": 120, "claim_rate": 0.5})

    # Composite risk score (0–10):
    # rain contributes up to 4 pts, heat up to 3 pts, AQI up to 2 pts, historical 1 pt
    rain_score = min(data["rainfall"] / 25, 1.0) * 4
    heat_score = max(0, (data["temperature"] - 35) / 10) * 3
    aqi_score  = min(data["aqi"] / 300, 1.0) * 2
    hist_score = city_info["claim_rate"] * 1

    score = round(rain_score + heat_score + aqi_score + hist_score, 1)
    score = min(score, 10.0)
    level = "CRITICAL" if score >= 7 else "MODERATE" if score >= 4 else "LOW"

    return {
        "score":       score,
        "level":       level,
        "breakdown": {
            "rain":        round(rain_score, 2),
            "heat":        round(heat_score, 2),
            "aqi":         round(aqi_score, 2),
            "historical":  round(hist_score, 2),
        },
    }


# ─── Wallet ───────────────────────────────────────────────────────────────────

@router.get("/wallet/{worker_id}")
def get_wallet(
    worker_id: int,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    worker = get_current_user(authorization, db)
    if worker.id != worker_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return {"balance": round(worker.wallet_balance, 2)}


# ─── Worker Stats ─────────────────────────────────────────────────────────────

@router.get("/workers/{worker_id}/stats")
def worker_stats(
    worker_id: int,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    worker = get_current_user(authorization, db)
    if worker.id != worker_id:
        raise HTTPException(status_code=403, detail="Access denied")

    claims = db.query(Claim).filter(Claim.worker_id == worker_id).order_by(Claim.created_at.desc()).all()
    total_payout = sum(c.amount for c in claims)

    return {
        "claims_count":   len(claims),
        "total_payouts":  round(total_payout, 2),
        "trust_score":    worker.trust_score,
        "wallet_balance": round(worker.wallet_balance, 2),
        "claims_history": [
            {
                "timestamp":    c.created_at.isoformat() if c.created_at else None,
                "trigger_type": c.trigger_type,
                "amount":       c.amount,
                "status":       c.status,
            }
            for c in claims[:20]
        ],
    }


# ─── Parametric Trigger ───────────────────────────────────────────────────────

class TriggerRequest(BaseModel):
    lat: Optional[float] = None
    lon: Optional[float] = None


@router.post("/check-and-trigger")
def check_and_trigger(
    req: TriggerRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Core parametric engine.
    Checks real weather against policy thresholds and auto-credits wallet.
    Includes: fraud check, GPS boundary check, proportional payout.
    """
    worker = get_current_user(authorization, db)

    policy = db.query(InsurancePolicy).filter(
        InsurancePolicy.worker_id == worker.id,
        InsurancePolicy.is_active == True,
    ).first()

    if not policy:
        return {"triggered": False, "reason": "No active policy. Purchase a plan first."}

    # Get real weather
    weather    = get_weather(worker.city)
    rainfall   = weather["rainfall"]
    temperature = weather["temperature"]

    # Fraud check
    claims_count  = db.query(Claim).filter(Claim.worker_id == worker.id).count()
    account_age   = max((utcnow() - worker.created_at).days, 1) if worker.created_at else 30
    claims_per_day = claims_count / account_age

    fraud_result = predict_fraud(rainfall, temperature, claims_count, account_age, claims_per_day)
    if fraud_result["is_fraud"]:
        worker.trust_score = max(0, worker.trust_score - 10)
        db.commit()
        return {
            "triggered": False,
            "reason":    f"Fraud detection: {fraud_result['reason']}",
            "fraud":     True,
        }

    # GPS boundary verification
    if req.lat is not None and req.lon is not None and worker.city in CITY_CENTERS:
        center  = CITY_CENTERS[worker.city]
        dist_sq = (req.lat - center["lat"]) ** 2 + (req.lon - center["lon"]) ** 2
        if dist_sq > GPS_BOUNDARY_THRESHOLD:
            worker.trust_score = max(0, worker.trust_score - 15)
            db.commit()
            return {
                "triggered": False,
                "reason":    f"GPS mismatch: you are outside {worker.city}'s coverage zone.",
                "gps_error": True,
            }
        worker.last_lat = req.lat
        worker.last_lon = req.lon
        db.commit()

    # Check parametric thresholds
    triggered    = False
    trigger_type = None
    payout       = 0.0

    if rainfall >= policy.rain_threshold:
        triggered    = True
        trigger_type = f"Heavy Rain ({rainfall}mm)"
        # Proportional payout: capped at max_payout
        ratio  = min(rainfall / policy.rain_threshold, 2.0)
        payout = min(policy.max_payout * ratio * 0.5, policy.max_payout)

    elif temperature >= policy.heat_threshold:
        triggered    = True
        trigger_type = f"Extreme Heat ({temperature}°C)"
        ratio  = min((temperature - policy.heat_threshold + 1) / 5, 1.5)
        payout = min(policy.max_payout * ratio * 0.4, policy.max_payout)

    if not triggered:
        return {
            "triggered": False,
            "reason":    (
                f"Thresholds not met — "
                f"Rain: {rainfall}mm (need ≥{policy.rain_threshold}mm), "
                f"Temp: {temperature}°C (need ≥{policy.heat_threshold}°C)"
            ),
            "current_weather": {"rain_mm": rainfall, "temp_celsius": temperature},
        }

    payout = round(payout, 2)
    worker.wallet_balance += payout
    worker.trust_score = min(100, worker.trust_score + 1)   # Good claim = slight trust boost

    claim = Claim(
        worker_id    = worker.id,
        trigger_type = trigger_type,
        amount       = payout,
        status       = "APPROVED",
        rainfall_mm  = rainfall,
        temp_celsius = temperature,
    )
    db.add(claim)

    # Update pool payouts for actuarial tracking
    pool = db.query(PremiumPool).filter(PremiumPool.city == worker.city).first()
    if pool:
        pool.total_payouts += payout
        if pool.total_premiums > 0:
            pool.reserve_ratio = round(pool.total_premiums / pool.total_payouts, 2)

    db.commit()

    return {
        "triggered":   True,
        "trigger_type": trigger_type,
        "payout":      payout,
        "new_balance": round(worker.wallet_balance, 2),
        "message":     f"✅ ₹{payout} credited to your wallet automatically!",
    }


# ─── Community ────────────────────────────────────────────────────────────────

class PostRequest(BaseModel):
    text: Optional[str] = None
    content: Optional[str] = None
    parent_id: Optional[int] = None


@router.get("/community/posts")
def get_posts(db: Session = Depends(get_db)):
    posts = db.query(CommunityPost).order_by(CommunityPost.created_at.desc()).all()

    from collections import defaultdict
    reply_map = defaultdict(list)
    for p in posts:
        if p.parent_id is not None:
            reply_map[p.parent_id].append(p)

    def _fmt(p):
        return {
            "id":              p.id,
            "author_name":     p.author,
            "author_city":     p.city or "Unknown",
            "author_platform": p.platform or "SafeFlow",
            "content":         p.text,
            "likes":           p.likes,
            "created_at":      p.created_at.isoformat() if p.created_at else None,
            "replies":         [_fmt(c) for c in reply_map.get(p.id, [])],
        }

    top_level = [p for p in posts if p.parent_id is None]
    return [_fmt(p) for p in top_level[:20]]


@router.post("/community/posts")
def create_post(
    req: PostRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    # Gracefully handle unauthenticated posts (community is semi-public)
    author, city, platform = "Anonymous Worker", "India", "SafeFlow"
    if authorization:
        try:
            worker = get_current_user(authorization, db)
            if worker:
                author, city, platform = worker.name, worker.city, worker.platform
        except Exception:
            pass

    text = req.text or req.content
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Post text cannot be empty")

    post = CommunityPost(author=author, text=text.strip(), city=city, platform=platform, parent_id=req.parent_id)
    db.add(post)
    db.commit()
    return {"status": "ok"}


@router.put("/community/posts/{post_id}/like")
def like_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    post.likes += 1
    db.commit()
    return {"status": "ok", "likes": post.likes}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _weather_summary(data: dict) -> str:
    if data["rainfall"] > 20:
        return "⛈️ Heavy Rain — Parametric trigger likely"
    if data["rainfall"] > 5:
        return "🌧️ Moderate Rain"
    if data["temperature"] > 42:
        return "🔥 Extreme Heat Warning"
    if data["temperature"] > 38:
        return "☀️ High Heat — Stay hydrated"
    return "✅ Clear conditions"
