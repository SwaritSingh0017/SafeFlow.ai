import base64
import json
import logging
import os
import firebase_admin
from firebase_admin import auth, credentials
from fastapi import HTTPException

logger = logging.getLogger("firebase_service")

_firebase_app = None

def get_firebase_app():
    global _firebase_app
    if _firebase_app:
        return _firebase_app
    if firebase_admin._apps:
        _firebase_app = firebase_admin.get_app()
        return _firebase_app

    credentials_payload = _load_credentials_payload()
    if not credentials_payload:
        raise RuntimeError("Firebase Admin credentials are not configured.")

    _firebase_app = firebase_admin.initialize_app(credentials.Certificate(credentials_payload))
    return _firebase_app


def verify_firebase_token(id_token: str) -> dict:
    try:
        app = get_firebase_app()
        decoded = auth.verify_id_token(id_token, app=app, check_revoked=False)
    except Exception as exc:
        logger.warning("Firebase token verification failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid Firebase ID token")

    phone_number = decoded.get("phone_number")
    uid = decoded.get("uid")
    if not phone_number or not uid:
        raise HTTPException(status_code=400, detail="Firebase token is missing required phone claims")

    return {
        "uid": uid,
        "phone_number": _normalize_phone(phone_number),
        "claims": decoded,
    }


def _load_credentials_payload():
    raw_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    raw_b64 = os.getenv("FIREBASE_SERVICE_ACCOUNT_BASE64", "").strip()
    path = os.getenv("FIREBASE_CREDENTIALS_PATH", "").strip()
    local_fallback = os.path.join(os.path.dirname(os.path.dirname(__file__)), "safeflow-firebase.json")

    if raw_json:
        return json.loads(raw_json)
    if raw_b64:
        return json.loads(base64.b64decode(raw_b64).decode("utf-8"))
    if path:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    if os.path.exists(local_fallback):
        with open(local_fallback, "r", encoding="utf-8") as handle:
            return json.load(handle)
    return None


def _normalize_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if digits.startswith("91") and len(digits) > 10:
        digits = digits[-10:]
    return digits
