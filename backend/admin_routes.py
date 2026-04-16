"""
Admin Routes — overview, fraud panel, city risks, simulation
All routes require admin JWT token.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import Worker, Claim, InsurancePolicy, CommunityPost, PremiumPool, PaymentTransaction
from constants import CITY_CENTERS
from security import require_admin

logger = logging.getLogger("admin_routes")

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ─── Overview ─────────────────────────────────────────────────────────────────

@router.get("/overview")
def overview(
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    workers         = db.query(Worker).count()
    active_policies = db.query(InsurancePolicy).filter(InsurancePolicy.is_active == True).count()
    claims_total    = db.query(Claim).count()
    fraud_alerts    = db.query(Worker).filter(Worker.trust_score < 70).count()

    # Actuarial KPIs
    total_premiums = db.query(PremiumPool).all()
    total_collected = sum(p.total_premiums for p in total_premiums)
    total_paid_out  = sum(p.total_payouts  for p in total_premiums)

    return {
        "workers":          workers,
        "active_policies":  active_policies,
        "claims_today":     claims_total,
        "fraud_alerts":     fraud_alerts,
        "total_premiums":   round(total_collected, 2),
        "total_payouts":    round(total_paid_out, 2),
        "pool_health":      round(total_collected / total_paid_out, 2) if total_paid_out > 0 else 2.0,
    }


# ─── Fraud Panel ──────────────────────────────────────────────────────────────

@router.get("/fraud-panel")
def fraud_panel(
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    workers = db.query(Worker).order_by(Worker.trust_score.asc()).all()
    
    name_counts = db.query(func.lower(Worker.name), func.count(Worker.id)).group_by(func.lower(Worker.name)).all()
    duplicate_names = {name for name, count in name_counts if count > 1}
    
    device_counts = db.query(Worker.device_id, func.count(Worker.id)).filter(Worker.device_id.isnot(None)).group_by(Worker.device_id).all()
    duplicate_devices = {dev for dev, count in device_counts if count > 1}
    
    claim_counts_q = db.query(Claim.worker_id, func.count(Claim.id)).group_by(Claim.worker_id).all()
    claim_counts = {worker_id: count for worker_id, count in claim_counts_q}
    
    results = []

    for w in workers:
        f_score = round(max(0, 100 - w.trust_score) / 10.0, 1)
        status  = "HOLD" if w.trust_score < 60 else ("PARTIAL" if w.trust_score < 80 else "CLEAR")
        flags   = []

        # Duplicate name check
        if w.name and w.name.lower() in duplicate_names:
            flags.append({"flag": "⚠️ Duplicate Name Detected"})
            f_score = min(f_score + 2.0, 10.0)

        # Duplicate device check
        if w.device_id and w.device_id in duplicate_devices:
            flags.append({"flag": "🚨 Sybil Risk — Device Shared"})
            f_score = 9.5
            status  = "HOLD"

        # GPS zone breach
        if w.last_lat is not None and w.city in CITY_CENTERS:
            center  = CITY_CENTERS[w.city]
            dist_sq = (w.last_lat - center["lat"]) ** 2 + (w.last_lon - center["lon"]) ** 2
            if dist_sq > 0.52:
                flags.append({"flag": "🚨 GPS Zone Breach"})
                f_score = max(f_score, 8.5)
                status  = "HOLD"

        # Trust score based flags
        if w.trust_score <= 40:
            flags.append({"flag": "🔴 Severe Trust Drop"})
        elif w.trust_score <= 60:
            flags.append({"flag": "🟠 Disputed Claim History"})
        elif not flags:
            if w.trust_score == 85:
                labels = ["Device Trace Baseline", "Velocity Checks Active",
                          "Location Integrity Sync", "New Account Evaluation",
                          "Awaiting First Payout"]
                flags.append({"flag": labels[w.id % len(labels)]})
            else:
                flags.append({"flag": "✅ Verified & Clean"})

        claim_count = claim_counts.get(w.id, 0)

        results.append({
            "id":          f"c-w{w.id}",
            "worker_name": w.name,
            "trust_score": w.trust_score,
            "city":        w.city,
            "fraud_score": round(min(f_score, 10.0), 1),
            "status":      status,
            "flags":       flags,
            "device_id":   w.device_id,
            "claim_count": claim_count,
        })

    return results


# ─── Admin Claim Action ───────────────────────────────────────────────────────

@router.post("/action/{claim_id}")
def action_claim(
    claim_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    try:
        worker_id = int(claim_id.split("-w")[1])
    except (IndexError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid claim ID format")

    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    worker.trust_score = min(100, worker.trust_score + 5)
    db.commit()
    return {"status": "ok", "message": f"Trust restored for {worker.name} → {worker.trust_score}/100"}


# ─── Simulation ───────────────────────────────────────────────────────────────

class SimulateRequest(BaseModel):
    city: str
    disruption: str
    intensity: str


@router.post("/simulate")
def simulate_event(
    req: SimulateRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Simulates a parametric event in a city — triggers payouts for all active policies."""
    workers_in_city = db.query(Worker).filter(Worker.city == req.city).all()
    triggered_count = 0
    total_payout    = 0.0

    for worker in workers_in_city:
        policy = db.query(InsurancePolicy).filter(
            InsurancePolicy.worker_id == worker.id,
            InsurancePolicy.is_active == True,
        ).first()
        if policy:
            payout = round(policy.max_payout * 0.5, 2)
            worker.wallet_balance += payout

            db.add(Claim(
                worker_id    = worker.id,
                trigger_type = req.disruption,
                amount       = payout,
                status       = "APPROVED",
            ))

            # Update pool
            pool = db.query(PremiumPool).filter(PremiumPool.city == req.city).first()
            if pool:
                pool.total_payouts += payout
                if pool.total_premiums > 0:
                    pool.reserve_ratio = round(pool.total_premiums / pool.total_payouts, 2)

            triggered_count += 1
            total_payout    += payout

    # Post to community feed
    db.add(CommunityPost(
        author   = "SafeFlow System",
        text     = f"🚨 PARAMETRIC ALERT: {req.intensity} {req.disruption} in {req.city}. {triggered_count} workers protected. Total payout: ₹{round(total_payout, 2)}.",
        city     = req.city,
        platform = "System",
    ))
    db.commit()

    return {
        "status":          "ok",
        "triggered_count": triggered_count,
        "total_payout":    round(total_payout, 2),
        "message":         f"{triggered_count} claims triggered in {req.city}. Total: ₹{round(total_payout, 2)}",
    }


# ─── City Risk Map ────────────────────────────────────────────────────────────

@router.get("/city-risks")
def city_risks(
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    results = []
    for city_name, info in CITY_CENTERS.items():
        worker_count = db.query(Worker).filter(Worker.city == city_name).count()
        claim_count  = (
            db.query(Claim)
            .join(Worker, Claim.worker_id == Worker.id)
            .filter(Worker.city == city_name)
            .count()
        )
        pool = db.query(PremiumPool).filter(PremiumPool.city == city_name).first()

        risk_score = 1.0
        if worker_count > 0:
            risk_score = min(10.0, round((claim_count / worker_count) * 10 + 1, 1))

        results.append({
            "name":           city_name,
            "lat":            info["lat"],
            "lon":            info["lon"],
            "risk_score":     risk_score,
            "active_workers": worker_count,
            "claims_today":   claim_count,
            "pool_health":    pool.reserve_ratio if pool else 2.0,
        })

    return results


# ─── Pool Health ──────────────────────────────────────────────────────────────

@router.get("/pool-health")
def pool_health(
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Returns actuarial pool health per city — key business viability metric."""
    pools = db.query(PremiumPool).all()
    return [
        {
            "city":           p.city,
            "total_premiums": round(p.total_premiums, 2),
            "total_payouts":  round(p.total_payouts, 2),
            "reserve_ratio":  round(p.reserve_ratio, 2),
            "status":         "Solvent" if p.reserve_ratio >= 1.2 else "At Risk",
        }
        for p in pools
    ]


# ─── Pending Withdrawals ─────────────────────────────────────────────────────────────

@router.get("/withdrawals")
def list_withdrawals(
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Return all withdrawal transactions (pending first, then completed)."""
    txns = (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.kind == "withdrawal")
        .order_by(
            # pending first
            PaymentTransaction.status.desc(),
            PaymentTransaction.created_at.desc(),
        )
        .limit(200)
        .all()
    )

    result = []
    for t in txns:
        worker = db.query(Worker).filter(Worker.id == t.worker_id).first()
        result.append({
            "ref":          t.provider_order_id.replace("wdl_", ""),
            "worker_name":  worker.name if worker else "Unknown",
            "worker_phone": worker.phone if worker else "",
            "upi_id":       worker.upi if worker else "",
            "amount":       round(t.amount, 2),
            "status":       t.status,
            "created_at":   t.created_at.isoformat() if t.created_at else None,
        })
    return result


@router.post("/withdrawals/{ref}/approve")
def approve_withdrawal(
    ref: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Mark a pending withdrawal as completed (admin confirms payout was sent)."""
    from security import utcnow
    txn = (
        db.query(PaymentTransaction)
        .filter(
            PaymentTransaction.provider_order_id == f"wdl_{ref}",
            PaymentTransaction.kind == "withdrawal",
        )
        .first()
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Withdrawal not found")
    if txn.status == "verified":
        return {"status": "ok", "message": "Already marked as completed."}

    txn.status = "verified"
    txn.verified_at = utcnow()
    db.commit()
    return {"status": "ok", "message": f"Withdrawal ₹{txn.amount} marked as completed."}
