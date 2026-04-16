from constants import INSURANCE_PLANS
from models import InsurancePolicy, PaymentTransaction, PremiumPool, Worker
from security import create_token_pair


def test_payment_verification_is_idempotent(client, monkeypatch):
    test_client, SessionLocal = client

    with SessionLocal() as db:
        worker = Worker(
            name="Pay QA",
            phone="8888888888",
            city="Mumbai",
            platform="Swiggy",
        )
        db.add(worker)
        db.commit()
        db.refresh(worker)
        worker_id = worker.id

        transaction = PaymentTransaction(
            worker_id=worker_id,
            kind="policy_purchase",
            status="created",
            provider_order_id="order_test_123",
            plan_type="Basic",
            amount=INSURANCE_PLANS["Basic"]["weekly_premium"],
        )
        db.add(transaction)
        db.commit()

        tokens = create_token_pair(str(worker_id), worker.role, db)

    monkeypatch.setattr("payment_routes._verify_signature", lambda *args, **kwargs: None)

    payload = {
        "razorpay_order_id": "order_test_123",
        "razorpay_payment_id": "pay_test_123",
        "razorpay_signature": "sig_test",
        "plan_type": "Basic",
    }
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    first = test_client.post("/api/payment/verify", json=payload, headers=headers)
    second = test_client.post("/api/payment/verify", json=payload, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200

    with SessionLocal() as db:
        transactions = db.query(PaymentTransaction).filter(PaymentTransaction.provider_order_id == "order_test_123").all()
        policies = db.query(InsurancePolicy).filter(InsurancePolicy.worker_id == worker_id).all()
        pool = db.query(PremiumPool).filter(PremiumPool.city == "Mumbai").first()

    assert len(transactions) == 1
    assert len(policies) == 1
    assert pool.total_premiums == INSURANCE_PLANS["Basic"]["weekly_premium"]


def test_local_demo_payment_fallback_activates_policy(client):
    test_client, SessionLocal = client

    with SessionLocal() as db:
        worker = Worker(
            name="Demo Checkout",
            phone="9999999999",
            city="Mumbai",
            platform="Swiggy",
        )
        db.add(worker)
        db.commit()
        db.refresh(worker)
        worker_id = worker.id
        tokens = create_token_pair(str(worker_id), worker.role, db)

    payload = {
        "kind": "policy_purchase",
        "plan_type": "Standard",
    }
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    response = test_client.post("/api/payment/dev-complete", json=payload, headers=headers)

    assert response.status_code == 200
    assert response.json()["mode"] == "demo"

    with SessionLocal() as db:
        policy = db.query(InsurancePolicy).filter(InsurancePolicy.worker_id == worker_id, InsurancePolicy.is_active == True).first()
        transaction = db.query(PaymentTransaction).filter(PaymentTransaction.worker_id == worker_id, PaymentTransaction.status == "verified").first()

    assert policy is not None
    assert policy.plan_type == "Standard"
    assert transaction is not None
