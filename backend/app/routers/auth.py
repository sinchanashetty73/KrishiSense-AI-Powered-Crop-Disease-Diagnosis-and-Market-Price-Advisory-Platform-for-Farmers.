import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import current_user
from ..models import OTP, User, utcnow
from ..schemas import OTPRequest, OTPVerify, TokenOut, UserOut, UserUpdate
from ..security import create_token
from ..services.sms import send_sms

router = APIRouter(tags=["auth"])


def _norm(phone: str) -> str:
    return phone.strip().replace(" ", "")


@router.post("/auth/request-otp")
def request_otp(body: OTPRequest, db: Session = Depends(get_db)):
    phone = _norm(body.phone)
    recent = (db.query(OTP).filter(OTP.phone == phone, OTP.expires_at > utcnow() + timedelta(minutes=4))
              .count())
    if recent >= 3:
        raise HTTPException(429, "Too many OTP requests. Try again in a few minutes.")
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(OTP(phone=phone, code=code, expires_at=utcnow() + timedelta(minutes=5)))
    db.commit()
    send_sms(phone, f"Your KrishiSense OTP is {code}. Valid for 5 minutes.")
    out = {"message": "OTP sent"}
    if settings.dev_otp_echo:
        out["dev_otp"] = code  # DEV ONLY. Disable with DEV_OTP_ECHO=false
    return out


@router.post("/auth/verify-otp", response_model=TokenOut)
def verify_otp(body: OTPVerify, db: Session = Depends(get_db)):
    phone = _norm(body.phone)
    otp = (db.query(OTP).filter(OTP.phone == phone, OTP.used.is_(False), OTP.expires_at > utcnow())
           .order_by(OTP.id.desc()).first())
    if otp is None or not secrets.compare_digest(otp.code, body.code):
        raise HTTPException(400, "Invalid or expired OTP")
    otp.used = True
    user = db.query(User).filter(User.phone == phone).first()
    if user is None:
        user = User(phone=phone, name=body.name, language=body.language)
        db.add(user)
    db.commit()
    return TokenOut(access_token=create_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(body: UserUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.add(user)
    db.commit()
    return user
