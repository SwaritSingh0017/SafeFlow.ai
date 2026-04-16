import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Header, HTTPException
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from constants import ADMIN_EMAIL_DEFAULT, ADMIN_PASSWORD_DEFAULT
from models import RefreshSession, Worker

logger = logging.getLogger("security")

JWT_SECRET = os.getenv("JWT_SECRET", "").strip()
JWT_ALGO = "HS256"
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "15"))
REFRESH_TOKEN_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "30"))
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", ADMIN_EMAIL_DEFAULT)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", ADMIN_PASSWORD_DEFAULT)

if not JWT_SECRET:
    logger.warning("JWT_SECRET is not configured. Using an insecure local fallback.")
    JWT_SECRET = "unsafe-local-secret-change-me"


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utcnow_aware() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(subject: str, role: str) -> str:
    now = utcnow_aware()
    payload = {
        "sub": str(subject),
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ACCESS_TOKEN_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def create_refresh_session(subject: str, role: str, db: Session) -> tuple[str, RefreshSession]:
    now = utcnow_aware()
    token_id = secrets.token_urlsafe(24)
    raw_secret = secrets.token_urlsafe(48)
    refresh_token = f"{token_id}.{raw_secret}"
    payload = {
        "sub": str(subject),
        "role": role,
        "type": "refresh",
        "sid": token_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=REFRESH_TOKEN_DAYS)).timestamp()),
    }
    signed_token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)
    session = RefreshSession(
        token_id=token_id,
        subject=str(subject),
        role=role,
        token_hash=_hash_token(refresh_token),
        expires_at=utcnow() + timedelta(days=REFRESH_TOKEN_DAYS),
    )
    db.add(session)
    db.flush()
    return f"{signed_token}.{raw_secret}", session


def create_token_pair(subject: str, role: str, db: Session) -> dict:
    access_token = create_access_token(subject, role)
    refresh_token, _ = create_refresh_session(subject, role, db)
    db.commit()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_MINUTES * 60,
    }


def decode_token(token: str, expected_type: Optional[str] = None) -> dict | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except JWTError:
        return None

    if expected_type and payload.get("type") != expected_type:
        return None
    return payload


def rotate_refresh_token(refresh_token: str, db: Session) -> dict | None:
    parsed = _split_refresh_token(refresh_token)
    if not parsed:
        return None

    signed_token, raw_secret = parsed
    payload = decode_token(signed_token, expected_type="refresh")
    if not payload:
        return None

    session = (
        db.query(RefreshSession)
        .filter(RefreshSession.token_id == payload.get("sid"))
        .first()
    )
    if not session or session.revoked_at is not None or session.expires_at <= utcnow():
        return None

    expected_hash = _hash_token(f"{payload.get('sid')}.{raw_secret}")
    if not hmac.compare_digest(session.token_hash, expected_hash):
        session.revoked_at = utcnow()
        db.commit()
        return None

    session.revoked_at = utcnow()
    return create_token_pair(payload["sub"], payload["role"], db)


def revoke_refresh_token(refresh_token: str, db: Session) -> None:
    parsed = _split_refresh_token(refresh_token)
    if not parsed:
        return

    signed_token, _ = parsed
    payload = decode_token(signed_token, expected_type="refresh")
    if not payload:
        return

    session = (
        db.query(RefreshSession)
        .filter(RefreshSession.token_id == payload.get("sid"))
        .first()
    )
    if session and session.revoked_at is None:
        session.revoked_at = utcnow()
        db.commit()


def get_current_user(
    authorization: Optional[str],
    db: Session,
    *,
    allow_admin: bool = False,
) -> Worker:
    token = extract_bearer_token(authorization)
    payload = decode_token(token, expected_type="access")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if payload.get("role") == "admin":
        if not allow_admin:
            raise HTTPException(status_code=403, detail="Admin access only")
        return _build_admin_user()

    worker = db.query(Worker).filter(Worker.id == int(payload["sub"])).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    return worker


def require_admin(
    authorization: Optional[str] = Header(None),
) -> dict:
    token = extract_bearer_token(authorization)
    payload = decode_token(token, expected_type="access")
    if not payload or payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access only")
    return payload


def extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    token = authorization.replace("Bearer ", "").strip()
    if not token or token in {"null", "undefined"}:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token


def _hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _split_refresh_token(token: str) -> tuple[str, str] | None:
    marker = token.rfind(".")
    if marker == -1:
        return None
    return token[:marker], token[marker + 1 :]


def _build_admin_user():
    class _Admin:
        id = 0
        name = "Admin"
        phone = ADMIN_EMAIL
        city = "Global"
        role = "admin"
        onboarding_complete = True

    return _Admin()
