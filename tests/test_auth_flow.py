def test_firebase_exchange_registers_and_refreshes(client, monkeypatch):
    test_client, _ = client

    monkeypatch.setattr(
        "auth_routes.verify_firebase_token",
        lambda token: {"uid": "firebase-uid-1", "phone_number": "9999900001", "claims": {}},
    )

    exchange_response = test_client.post(
        "/api/auth/firebase/exchange",
        json={
            "firebase_token": "firebase-token-1234567890",
            "name": "Auth QA",
            "city": "Mumbai",
            "platform": "Swiggy",
            "avg_daily_income": 850,
            "platform_hours": 8,
            "device_id": "device-auth-qa",
        },
    )
    assert exchange_response.status_code == 200
    tokens = exchange_response.json()

    access_header = {"Authorization": f"Bearer {tokens['access_token']}"}
    me_response = test_client.get("/api/auth/me", headers=access_header)
    assert me_response.status_code == 200
    assert me_response.json()["phone"] == "9999900001"

    refresh_response = test_client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 200
    assert "access_token" in refresh_response.json()


def test_firebase_exchange_requires_registration_data_for_new_user(client, monkeypatch):
    test_client, _ = client

    monkeypatch.setattr(
        "auth_routes.verify_firebase_token",
        lambda token: {"uid": "firebase-uid-2", "phone_number": "8888888888", "claims": {}},
    )

    response = test_client.post(
        "/api/auth/firebase/exchange",
        json={"firebase_token": "firebase-token-2234567890"},
    )
    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["code"] == "registration_required"


def test_protected_route_rejects_missing_token(client):
    test_client, _ = client
    response = test_client.get("/api/auth/me")
    assert response.status_code == 401
