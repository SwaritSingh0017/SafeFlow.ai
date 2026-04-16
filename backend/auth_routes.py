import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from constants import CITY_CENTERS, DEMO_PHONES, GPS_BOUNDARY_THRESHOLD
from database import get_db
from firebase_service import verify_firebase_token
from models import Worker
from otp_service import normalize_phone, send_otp, verify_otp
from security import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    create_token_pair,
    get_current_user,
    revoke_refresh_token,
    rotate_refresh_token,
)

logger = logging.getLogger("auth_routes")

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AdminLoginRequest(BaseModel):
    email: str
    password: str


class FirebaseExchangeRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    firebase_token: str = Field(min_length=20)
    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    city: Optional[str] = Field(default=None, min_length=2, max_length=80)
    platform: Optional[str] = Field(default=None, min_length=2, max_length=50)
    avg_daily_income: float = Field(default=800, ge=100, le=10000)
    platform_hours: float = Field(default=8, ge=1, le=18)
    device_id: str = Field(default="", max_length=120)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lon: Optional[float] = Field(default=None, ge=-180, le=180)


class OTPRequest(BaseModel):
    phone: str = Field(min_length=10, max_length=20)


class OTPVerifyRequest(BaseModel):
    phone: str = Field(min_length=10, max_length=20)
    otp: str = Field(min_length=6, max_length=6)


class RegisterRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=10, max_length=20)
    city: str = Field(min_length=2, max_length=80)
    platform: str = Field(min_length=2, max_length=50)
    avg_daily_income: float = Field(default=800, ge=100, le=10000)
    platform_hours: float = Field(default=8, ge=1, le=18)
    device_id: str = Field(default="", max_length=120)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lon: Optional[float] = Field(default=None, ge=-180, le=180)
    otp: str = Field(min_length=6, max_length=6)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    city: Optional[str] = Field(default=None, min_length=2, max_length=80)
    upi: Optional[str] = Field(default=None, max_length=120)


@router.post("/admin/login")
def admin_login(req: AdminLoginRequest, db: Session = Depends(get_db)):
    if req.email != ADMIN_EMAIL or req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    return create_token_pair("0", "admin", db)


@router.post("/send-otp")
def send_otp_route(req: OTPRequest, db: Session = Depends(get_db)):
    result = send_otp(req.phone, db=db)
    if not result["success"]:
        raise HTTPException(status_code=429, detail=result.get("error", "Failed to send OTP"))
    return result


@router.post("/verify-otp")
def verify_otp_route(req: OTPVerifyRequest, db: Session = Depends(get_db)):
    if not verify_otp(req.phone, req.otp, db=db):
        raise HTTPException(status_code=401, detail="Invalid or expired OTP")

    phone = normalize_phone(req.phone)
    worker = db.query(Worker).filter(Worker.phone == phone).first()
    if not worker:
        if phone in DEMO_PHONES or f"+91{phone}" in DEMO_PHONES:
            worker = Worker(
                name="Demo Worker",
                phone=phone,
                firebase_uid=f"phone:{phone}",
                city="Mumbai",
                platform="Swiggy",
                avg_daily_income=800,
                platform_hours=8,
            )
            db.add(worker)
            db.commit()
            db.refresh(worker)
        else:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "registration_required",
                    "message": "Phone verified but worker profile does not exist.",
                    "phone": phone,
                },
            )

    if not worker.firebase_uid:
        worker.firebase_uid = f"phone:{worker.phone}"
        db.commit()
        db.refresh(worker)

    return {**create_token_pair(str(worker.id), worker.role, db), "worker": _worker_dict(worker)}


@router.post("/firebase/exchange")
def firebase_exchange(req: FirebaseExchangeRequest, db: Session = Depends(get_db)):
    firebase_identity = verify_firebase_token(req.firebase_token)
    worker = (
        db.query(Worker)
        .filter(
            (Worker.firebase_uid == firebase_identity["uid"])
            | (Worker.phone == firebase_identity["phone_number"])
        )
        .first()
    )

    if worker:
        if not worker.firebase_uid:
            worker.firebase_uid = firebase_identity["uid"]
            db.commit()
            db.refresh(worker)
        return {**create_token_pair(str(worker.id), worker.role, db), "worker": _worker_dict(worker)}

    missing_fields = [
        field
        for field in ("name", "city", "platform")
        if not getattr(req, field)
    ]
    if missing_fields:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "registration_required",
                "message": "Firebase identity verified but worker profile does not exist.",
                "missing_fields": missing_fields,
                "phone": firebase_identity["phone_number"],
            },
        )

    if req.city not in CITY_CENTERS:
        raise HTTPException(status_code=400, detail=f"City '{req.city}' is not in our coverage zone yet.")

    if req.device_id:
        dup_device = (
            db.query(Worker)
            .filter(Worker.device_id == req.device_id, Worker.device_id != "")
            .first()
        )
        if dup_device:
            raise HTTPException(
                status_code=403,
                detail=f"Anti-fraud: this device is already linked to '{dup_device.name}'.",
            )

    if req.lat is not None and req.lon is not None:
        center = CITY_CENTERS[req.city]
        dist_sq = (req.lat - center["lat"]) ** 2 + (req.lon - center["lon"]) ** 2
        if dist_sq > GPS_BOUNDARY_THRESHOLD:
            raise HTTPException(
                status_code=403,
                detail=f"Location mismatch: your GPS does not match {req.city}.",
            )

    worker = Worker(
        name=req.name,
        phone=firebase_identity["phone_number"],
        firebase_uid=firebase_identity["uid"],
        city=req.city,
        platform=req.platform,
        avg_daily_income=req.avg_daily_income,
        platform_hours=req.platform_hours,
        device_id=req.device_id or None,
        last_lat=req.lat,
        last_lon=req.lon,
    )
    db.add(worker)
    db.commit()
    db.refresh(worker)
    return {**create_token_pair(str(worker.id), worker.role, db), "worker": _worker_dict(worker)}


@router.post("/register")
def register_with_otp(req: RegisterRequest, db: Session = Depends(get_db)):
    if not verify_otp(req.phone, req.otp, db=db):
        raise HTTPException(status_code=401, detail="Invalid or expired OTP")

    phone = normalize_phone(req.phone)
    if db.query(Worker).filter(Worker.phone == phone).first():
        raise HTTPException(status_code=400, detail="Phone already registered. Please log in.")

    if req.city not in CITY_CENTERS:
        raise HTTPException(status_code=400, detail=f"City '{req.city}' is not in our coverage zone yet.")

    if req.device_id:
        dup_device = (
            db.query(Worker)
            .filter(Worker.device_id == req.device_id, Worker.device_id != "")
            .first()
        )
        if dup_device:
            raise HTTPException(
                status_code=403,
                detail=f"Anti-fraud: this device is already linked to '{dup_device.name}'.",
            )

    if req.lat is not None and req.lon is not None:
        center = CITY_CENTERS[req.city]
        dist_sq = (req.lat - center["lat"]) ** 2 + (req.lon - center["lon"]) ** 2
        if dist_sq > GPS_BOUNDARY_THRESHOLD:
            raise HTTPException(
                status_code=403,
                detail=f"Location mismatch: your GPS does not match {req.city}.",
            )

    worker = Worker(
        name=req.name,
        phone=phone,
        firebase_uid=f"phone:{phone}",
        city=req.city,
        platform=req.platform,
        avg_daily_income=req.avg_daily_income,
        platform_hours=req.platform_hours,
        device_id=req.device_id or None,
        last_lat=req.lat,
        last_lon=req.lon,
    )
    db.add(worker)
    db.commit()
    db.refresh(worker)
    return {**create_token_pair(str(worker.id), worker.role, db), "worker": _worker_dict(worker)}


@router.post("/refresh")
def refresh_session(req: RefreshRequest, db: Session = Depends(get_db)):
    tokens = rotate_refresh_token(req.refresh_token, db)
    if not tokens:
        raise HTTPException(status_code=401, detail="Refresh session expired. Please log in again.")
    return tokens


@router.post("/logout")
def logout(req: LogoutRequest, db: Session = Depends(get_db)):
    if req.refresh_token:
        revoke_refresh_token(req.refresh_token, db)
    return {"success": True}


@router.get("/me")
def get_me(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    user = get_current_user(authorization, db, allow_admin=True)
    return _worker_dict(user)


@router.put("/profile")
def update_profile(
    req: ProfileUpdateRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    worker = get_current_user(authorization, db)
    if req.name:
        worker.name = req.name
    if req.city:
        if req.city not in CITY_CENTERS:
            raise HTTPException(status_code=400, detail="Selected city is outside coverage.")
        worker.city = req.city
    if req.upi is not None:
        worker.upi = req.upi or None

    db.commit()
    db.refresh(worker)
    return {"success": True, "worker": _worker_dict(worker)}


def _worker_dict(worker) -> dict:
    return {
        "id": worker.id,
        "name": worker.name,
        "phone": worker.phone,
        "city": worker.city,
        "upi": getattr(worker, "upi", None),
        "role": worker.role,
        "onboarding_complete": worker.onboarding_complete,
    }
