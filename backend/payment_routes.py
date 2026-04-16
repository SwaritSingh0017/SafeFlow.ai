import hashlib
import hmac
import logging
import os
import re
import secrets
from typing import Optional

import razorpay
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from constants import DEMO_PHONES, INSURANCE_PLANS
from database import get_db
from models import InsurancePolicy, PaymentTransaction, PremiumPool
from security import get_current_user, utcnow

load_dotenv()

logger = logging.getLogger("payment_routes")

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

router = APIRouter(prefix="/api/payment", tags=["payment"])


class CreateOrderRequest(BaseModel):
    plan_type: str


class WalletFundRequest(BaseModel):
    amount: float = Field(gt=0, le=50000)


class VerifyWalletRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    amount: float = Field(gt=0, le=50000)


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    plan_type: str


class WebhookRequest(BaseModel):
    event: str
    payload: dict


class WithdrawRequest(BaseModel):
    amount: float = Field(gt=9.99, le=10000, description="Withdrawal amount (₹10–₹10,000 per request)")
    upi_id: str = Field(min_length=5, max_length=60, description="Destination UPI ID, e.g. name@upi")


class DevCompleteRequest(BaseModel):
    kind: str
    plan_type: Optional[str] = None
    amount: Optional[float] = Field(default=None, gt=0, le=50000)


def _get_razorpay_client():
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Payment gateway not configured. Set Razorpay credentials in the environment.",
        )
    return razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


@router.get("/config")
def get_payment_config():
    return {"key_id": RAZORPAY_KEY_ID, "currency": "INR"}


@router.post("/create-order")
def create_order(
    req: CreateOrderRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    if req.plan_type not in INSURANCE_PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan type")

    worker = get_current_user(authorization, db)
    plan = INSURANCE_PLANS[req.plan_type]
    amount_paise = int(plan["weekly_premium"] * 100)
    client = _get_razorpay_client()

    order = client.order.create(
        {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": f"sf_plan_{worker.id}_{secrets.token_hex(4)}",
            "notes": {
                "worker_id": str(worker.id),
                "plan_type": req.plan_type,
                "kind": "policy_purchase",
            },
        }
    )
    db.add(
        PaymentTransaction(
            worker_id=worker.id,
            kind="policy_purchase",
            status="created",
            provider_order_id=order["id"],
            plan_type=req.plan_type,
            amount=plan["weekly_premium"],
        )
    )
    db.commit()

    return {
        "order_id": order["id"],
        "amount": amount_paise,
        "currency": "INR",
        "plan_type": req.plan_type,
        "key_id": RAZORPAY_KEY_ID,
    }


@router.post("/create-wallet-order")
def create_wallet_order(
    req: WalletFundRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    worker = get_current_user(authorization, db)
    amount_paise = int(req.amount * 100)
    client = _get_razorpay_client()

    order = client.order.create(
        {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": f"sf_wallet_{worker.id}_{secrets.token_hex(4)}",
            "notes": {
                "worker_id": str(worker.id),
                "kind": "wallet_topup",
            },
        }
    )
    db.add(
        PaymentTransaction(
            worker_id=worker.id,
            kind="wallet_topup",
            status="created",
            provider_order_id=order["id"],
            amount=req.amount,
        )
    )
    db.commit()

    return {
        "order_id": order["id"],
        "amount": amount_paise,
        "currency": "INR",
        "key_id": RAZORPAY_KEY_ID,
    }


@router.post("/verify")
def verify_payment(
    req: VerifyPaymentRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    worker = get_current_user(authorization, db)
    transaction = _get_transaction(req.razorpay_order_id, worker.id, "policy_purchase", db)

    if transaction.status == "verified":
        policy = _get_active_policy(worker.id, db)
        return {
            "status": "success",
            "message": f"{transaction.plan_type} plan already activated for this payment.",
            "plan": transaction.plan_type,
            "max_payout": policy.max_payout if policy else INSURANCE_PLANS[transaction.plan_type]["max_payout"],
        }

    if req.plan_type != transaction.plan_type:
        raise HTTPException(status_code=400, detail="Payment plan does not match the original order.")

    _verify_signature(req.razorpay_order_id, req.razorpay_payment_id, req.razorpay_signature)
    _ensure_unique_payment_id(req.razorpay_payment_id, db)

    plan = INSURANCE_PLANS[req.plan_type]
    _activate_policy(worker.id, worker.city, req.plan_type, req.razorpay_order_id, plan, db)
    transaction.provider_payment_id = req.razorpay_payment_id
    transaction.status = "verified"
    transaction.verified_at = utcnow()
    db.commit()

    return {
        "status": "success",
        "message": f"{req.plan_type} plan activated. Payment verified.",
        "plan": req.plan_type,
        "max_payout": plan["max_payout"],
    }


@router.post("/verify-wallet")
def verify_wallet(
    req: VerifyWalletRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    worker = get_current_user(authorization, db)
    transaction = _get_transaction(req.razorpay_order_id, worker.id, "wallet_topup", db)

    if transaction.status == "verified":
        return {
            "status": "success",
            "message": f"Payment already processed. Current wallet balance is {round(worker.wallet_balance, 2)}.",
            "new_balance": round(worker.wallet_balance, 2),
        }

    _verify_signature(req.razorpay_order_id, req.razorpay_payment_id, req.razorpay_signature)
    _ensure_unique_payment_id(req.razorpay_payment_id, db)

    worker.wallet_balance += req.amount
    transaction.provider_payment_id = req.razorpay_payment_id
    transaction.status = "verified"
    transaction.verified_at = utcnow()
    db.commit()

    return {
        "status": "success",
        "message": f"Rs {req.amount} successfully added to your wallet.",
        "new_balance": round(worker.wallet_balance, 2),
    }


# ─── Withdrawal ───────────────────────────────────────────────────────────────

_UPI_RE = re.compile(r"^[a-zA-Z0-9._+-]+@[a-zA-Z]{3,}$")


@router.post("/withdraw")
def request_withdrawal(
    req: WithdrawRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Deduct amount from the worker's wallet and create a withdrawal transaction
    (status='pending'). A background job / admin triggers the actual UPI payout
    via Razorpay Payouts API. The worker's balance is debited immediately so
    they cannot double-spend.
    """
    worker = get_current_user(authorization, db)

    # Validate UPI format
    if not _UPI_RE.match(req.upi_id.strip()):
        raise HTTPException(
            status_code=400,
            detail="Invalid UPI ID format. Expected format: name@bankname",
        )

    if worker.wallet_balance < req.amount:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Insufficient wallet balance. "
                f"Available: ₹{round(worker.wallet_balance, 2)}, "
                f"Requested: ₹{req.amount}."
            ),
        )

    # Debit wallet immediately to prevent double-spend
    worker.wallet_balance -= req.amount
    worker.upi = req.upi_id.strip()   # persist / update UPI for next time

    txn_ref = secrets.token_hex(8)
    db.add(
        PaymentTransaction(
            worker_id=worker.id,
            kind="withdrawal",
            status="pending",
            provider_order_id=f"wdl_{txn_ref}",
            amount=req.amount,
        )
    )
    db.commit()

    logger.info(
        "Withdrawal requested: worker_id=%s amount=%.2f upi=%s ref=%s",
        worker.id, req.amount, req.upi_id, txn_ref,
    )

    return {
        "status": "success",
        "message": (
            f"₹{req.amount:.2f} withdrawal initiated to {req.upi_id}. "
            "Funds will arrive in your UPI account within 24 hours."
        ),
        "reference": txn_ref,
        "new_balance": round(worker.wallet_balance, 2),
    }


@router.post("/wallet-pay")
def pay_via_wallet(
    req: CreateOrderRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    worker = get_current_user(authorization, db)
    if req.plan_type not in INSURANCE_PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan type")

    plan = INSURANCE_PLANS[req.plan_type]
    if worker.wallet_balance < plan["weekly_premium"]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Insufficient wallet balance. Need Rs {plan['weekly_premium']}, "
                f"have Rs {round(worker.wallet_balance, 2)}."
            ),
        )

    worker.wallet_balance -= plan["weekly_premium"]
    _activate_policy(worker.id, worker.city, req.plan_type, None, plan, db)
    db.add(
        PaymentTransaction(
            worker_id=worker.id,
            kind="wallet_deduction",
            status="verified",
            plan_type=req.plan_type,
            amount=plan["weekly_premium"],
            verified_at=utcnow(),
        )
    )
    db.commit()
    return {
        "status": "success",
        "message": f"{req.plan_type} plan activated via wallet.",
        "plan": req.plan_type,
        "new_balance": round(worker.wallet_balance, 2),
        "max_payout": plan["max_payout"],
    }


@router.post("/webhook")
async def payment_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    body = await request.body()
    if RAZORPAY_WEBHOOK_SECRET and x_razorpay_signature:
        expected = hmac.new(
            RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, x_razorpay_signature):
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    payload_json = await request.json()
    if payload_json.get("event") != "payment.captured":
        return {"success": True, "ignored": True}

    payment = (((payload_json.get("payload") or {}).get("payment") or {}).get("entity") or {})
    order_id = payment.get("order_id")
    payment_id = payment.get("id")
    if not order_id or not payment_id:
        raise HTTPException(status_code=400, detail="Missing payment payload")

    transaction = db.query(PaymentTransaction).filter(PaymentTransaction.provider_order_id == order_id).first()
    if not transaction or transaction.status == "verified":
        return {"success": True, "ignored": True}

    transaction.provider_payment_id = payment_id
    transaction.status = "captured"
    transaction.verified_at = utcnow()
    db.commit()
    return {"success": True}


@router.post("/dev-complete")
def complete_demo_payment(
    req: DevCompleteRequest,
    request: Request,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    worker = get_current_user(authorization, db)
    _ensure_local_demo_payment(request, worker.phone)

    if req.kind == "policy_purchase":
        if not req.plan_type or req.plan_type not in INSURANCE_PLANS:
            raise HTTPException(status_code=400, detail="Invalid plan type")

        plan = INSURANCE_PLANS[req.plan_type]
        order_id = f"dev_order_{secrets.token_hex(8)}"
        payment_id = f"dev_pay_{secrets.token_hex(8)}"
        _activate_policy(worker.id, worker.city, req.plan_type, order_id, plan, db)
        db.add(
            PaymentTransaction(
                worker_id=worker.id,
                kind="policy_purchase",
                status="verified",
                provider_order_id=order_id,
                provider_payment_id=payment_id,
                plan_type=req.plan_type,
                amount=plan["weekly_premium"],
                verified_at=utcnow(),
            )
        )
        db.commit()
        return {
            "status": "success",
            "message": f"{req.plan_type} plan activated in local demo mode.",
            "plan": req.plan_type,
            "max_payout": plan["max_payout"],
            "mode": "demo",
        }

    if req.kind == "wallet_topup":
        if req.amount is None:
            raise HTTPException(status_code=400, detail="Amount is required for wallet top-ups")

        worker.wallet_balance += req.amount
        db.add(
            PaymentTransaction(
                worker_id=worker.id,
                kind="wallet_topup",
                status="verified",
                provider_order_id=f"dev_wallet_order_{secrets.token_hex(8)}",
                provider_payment_id=f"dev_wallet_pay_{secrets.token_hex(8)}",
                amount=req.amount,
                verified_at=utcnow(),
            )
        )
        db.commit()
        return {
            "status": "success",
            "message": f"Rs {req.amount} added to your wallet in local demo mode.",
            "new_balance": round(worker.wallet_balance, 2),
            "mode": "demo",
        }

    raise HTTPException(status_code=400, detail="Unsupported demo payment kind")


def _get_transaction(order_id: str, worker_id: int, kind: str, db: Session) -> PaymentTransaction:
    transaction = (
        db.query(PaymentTransaction)
        .filter(
            PaymentTransaction.provider_order_id == order_id,
            PaymentTransaction.worker_id == worker_id,
            PaymentTransaction.kind == kind,
        )
        .first()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Payment order not found.")
    return transaction


def _ensure_local_demo_payment(request: Request, phone: str) -> None:
    client_host = (request.client.host if request.client else "") or ""
    if client_host not in {"127.0.0.1", "localhost", "::1", "testclient"} or phone not in DEMO_PHONES:
        raise HTTPException(
            status_code=403,
            detail="Local demo payment fallback is only available for demo accounts on localhost.",
        )


def _verify_signature(order_id: str, payment_id: str, signature: str) -> None:
    if not RAZORPAY_KEY_SECRET:
        raise HTTPException(status_code=503, detail="Payment verification is unavailable.")
    expected_sig = hmac.new(
        RAZORPAY_KEY_SECRET.encode("utf-8"),
        f"{order_id}|{payment_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_sig, signature):
        raise HTTPException(status_code=400, detail="Payment verification failed: invalid signature")


def _ensure_unique_payment_id(payment_id: str, db: Session) -> None:
    existing = (
        db.query(PaymentTransaction)
        .filter(
            PaymentTransaction.provider_payment_id == payment_id,
            PaymentTransaction.status == "verified",
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="This payment has already been processed.")


def _activate_policy(worker_id: int, city: str, plan_type: str, order_id: Optional[str], plan: dict, db: Session) -> None:
    db.query(InsurancePolicy).filter(
        InsurancePolicy.worker_id == worker_id,
        InsurancePolicy.is_active == True,
    ).update({"is_active": False})

    policy = InsurancePolicy(
        worker_id=worker_id,
        plan_type=plan_type,
        weekly_premium=plan["weekly_premium"],
        max_payout=plan["max_payout"],
        rain_threshold=plan["rain_threshold"],
        heat_threshold=plan["heat_threshold"],
        aqi_threshold=plan["aqi_threshold"],
        civil_coverage=plan["civil_coverage"],
        razorpay_order_id=order_id,
        is_active=True,
    )
    db.add(policy)

    pool = db.query(PremiumPool).filter(PremiumPool.city == city).first()
    if not pool:
        pool = PremiumPool(city=city, total_premiums=0.0, total_payouts=0.0)
        db.add(pool)
        db.flush()
    pool.total_premiums += plan["weekly_premium"]
    _recalculate_reserve(pool)


def _get_active_policy(worker_id: int, db: Session) -> Optional[InsurancePolicy]:
    return (
        db.query(InsurancePolicy)
        .filter(InsurancePolicy.worker_id == worker_id, InsurancePolicy.is_active == True)
        .first()
    )


def _recalculate_reserve(pool: PremiumPool):
    if pool.total_payouts > 0:
        pool.reserve_ratio = round(pool.total_premiums / pool.total_payouts, 2)
    else:
        pool.reserve_ratio = 2.0
