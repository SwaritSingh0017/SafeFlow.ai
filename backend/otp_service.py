import hashlib
import hmac
import logging
import os
import random
from datetime import timedelta

from dotenv import load_dotenv

from models import OTPRecord, OTPThrottle
from security import utcnow

load_dotenv()

logger = logging.getLogger("otp_service")

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_VSID = os.getenv("TWILIO_VERIFY_SID", "")
OTP_PEPPER = os.getenv("OTP_PEPPER", os.getenv("JWT_SECRET", "unsafe-otp-pepper"))
OTP_TTL_MINUTES = int(os.getenv("OTP_TTL_MINUTES", "10"))
OTP_RESEND_COOLDOWN_SECONDS = int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", "30"))
OTP_MAX_FAILED_ATTEMPTS = int(os.getenv("OTP_MAX_FAILED_ATTEMPTS", "5"))
OTP_LOCK_MINUTES = int(os.getenv("OTP_LOCK_MINUTES", "15"))


def _twilio_client():
    from twilio.rest import Client

    return Client(TWILIO_SID, TWILIO_TOKEN)


def _normalize(phone: str) -> tuple[str, str]:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if digits.startswith("91") and len(digits) > 10:
        digits = digits[-10:]
    return f"+91{digits}", digits


def normalize_phone(phone: str) -> str:
    return _normalize(phone)[1]


def _has_twilio() -> bool:
    return bool(TWILIO_SID and TWILIO_TOKEN and TWILIO_VSID)


def send_otp(phone: str, db=None) -> dict:
    from constants import DEMO_PHONES

    normalized, raw = _normalize(phone)
    if raw in DEMO_PHONES or normalized in DEMO_PHONES:
        logger.info("[OTP] Demo phone %s accepted without external delivery", raw)
        return {
            "success": True,
            "method": "demo",
            "expires_in": OTP_TTL_MINUTES * 60,
            "retry_after": 0,
        }

    if db is None:
        return {"success": False, "error": "Database session is required for OTP delivery"}

    throttle = _get_throttle(db, normalized)
    now = utcnow()
    if throttle.locked_until and throttle.locked_until > now:
        retry_after = int((throttle.locked_until - now).total_seconds())
        return {
            "success": False,
            "error": "Too many invalid OTP attempts. Please wait before retrying.",
            "code": "otp_locked",
            "retry_after": max(retry_after, 1),
        }

    if throttle.resend_available_at and throttle.resend_available_at > now:
        retry_after = int((throttle.resend_available_at - now).total_seconds())
        return {
            "success": False,
            "error": "Please wait before requesting another OTP.",
            "code": "otp_cooldown",
            "retry_after": max(retry_after, 1),
        }

    expires_at = (now + timedelta(minutes=OTP_TTL_MINUTES)).replace(microsecond=0)

    if _has_twilio():
        try:
            verification = (
                _twilio_client()
                .verify.v2.services(TWILIO_VSID)
                .verifications.create(to=normalized, channel="sms")
            )
            if verification.status == "pending":
                logger.info("[OTP] Twilio verification started for %s", normalized)
                throttle.last_sent_at = now
                throttle.resend_available_at = now + timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS)
                throttle.failed_attempts = 0
                throttle.locked_until = None
                db.commit()
                return {
                    "success": True,
                    "method": "twilio",
                    "expires_in": OTP_TTL_MINUTES * 60,
                    "retry_after": OTP_RESEND_COOLDOWN_SECONDS,
                }
        except Exception as exc:
            logger.warning("[OTP] Twilio send failed for %s: %s", normalized, exc)

    otp_code = f"{random.randint(100000, 999999):06d}"
    otp_hash = _hash_otp(normalized, otp_code, expires_at.isoformat())

    db.query(OTPRecord).filter(OTPRecord.phone == normalized, OTPRecord.used == False).delete()
    db.add(
        OTPRecord(
            phone=normalized,
            otp=otp_hash,
            expires_at=expires_at,
            used=False,
        )
    )

    throttle.last_sent_at = now
    throttle.resend_available_at = now + timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS)
    throttle.failed_attempts = 0
    throttle.locked_until = None
    db.commit()

    logger.warning("[OTP] Fallback OTP issued for %s: %s", normalized, otp_code)
    return {
        "success": True,
        "method": "fallback",
        "expires_in": OTP_TTL_MINUTES * 60,
        "retry_after": OTP_RESEND_COOLDOWN_SECONDS,
    }


def verify_otp(phone: str, otp: str, db=None) -> bool:
    from constants import DEMO_OTP, DEMO_PHONES

    normalized, raw = _normalize(phone)
    if raw in DEMO_PHONES or normalized in DEMO_PHONES:
        return otp == DEMO_OTP

    if db is None:
        return False

    throttle = _get_throttle(db, normalized)
    now = utcnow()
    if throttle.locked_until and throttle.locked_until > now:
        return False

    if _has_twilio():
        try:
            result = (
                _twilio_client()
                .verify.v2.services(TWILIO_VSID)
                .verification_checks.create(to=normalized, code=otp)
            )
            if result.status == "approved":
                throttle.failed_attempts = 0
                throttle.locked_until = None
                db.commit()
                return True
        except Exception as exc:
            logger.warning("[OTP] Twilio verification failed for %s: %s", normalized, exc)
        
        # Bypassing DB check because we rely entirely on Twilio
    else:
        record = (
            db.query(OTPRecord)
            .filter(
                OTPRecord.phone == normalized,
                OTPRecord.used == False,
                OTPRecord.expires_at > now,
            )
            .order_by(OTPRecord.created_at.desc())
            .first()
        )
        if not record:
            return False

        expected_hash = _hash_otp(normalized, otp, record.expires_at.isoformat())
        if hmac.compare_digest(expected_hash, record.otp):
            record.used = True
            throttle.failed_attempts = 0
            throttle.locked_until = None
            db.commit()
            return True

    throttle.failed_attempts = (throttle.failed_attempts or 0) + 1
    if throttle.failed_attempts >= OTP_MAX_FAILED_ATTEMPTS:
        throttle.locked_until = now + timedelta(minutes=OTP_LOCK_MINUTES)
    db.commit()
    return False


def _get_throttle(db, normalized_phone: str) -> OTPThrottle:
    throttle = db.query(OTPThrottle).filter(OTPThrottle.phone == normalized_phone).first()
    if throttle:
        return throttle

    throttle = OTPThrottle(phone=normalized_phone)
    db.add(throttle)
    db.flush()
    return throttle


def _hash_otp(phone: str, otp: str, expires_at: str) -> str:
    value = f"{phone}:{otp}:{expires_at}:{OTP_PEPPER}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
