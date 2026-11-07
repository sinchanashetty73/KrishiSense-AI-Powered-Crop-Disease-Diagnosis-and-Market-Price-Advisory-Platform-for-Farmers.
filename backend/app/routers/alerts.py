from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import current_user
from ..models import Alert, AlertLog, Crop, Market, PushSubscription, User, utcnow
from ..schemas import AlertIn, AlertOut, PushSubscribeIn
from ..services import push, sms
from ..services.alert_dispatch import TEST_MESSAGE, _log
from ..services.alerting import evaluate

router = APIRouter(tags=["alerts"])


def _to_out(db: Session, a: Alert) -> AlertOut:
    ev = evaluate(db, a)
    return AlertOut(id=a.id, crop_id=a.crop_id, crop=db.get(Crop, a.crop_id).name, market_id=a.market_id,
                    market=db.get(Market, a.market_id).name, direction=a.direction, threshold=a.threshold,
                    current_price=ev["current_price"], change_pct=ev["change_pct"], triggered=ev["triggered"],
                    notify_sms=a.notify_sms, notify_push=a.notify_push)


@router.post("/alerts", response_model=AlertOut)
def create(body: AlertIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.get(Crop, body.crop_id) is None or db.get(Market, body.market_id) is None:
        raise HTTPException(404, "Unknown crop or market")
    if body.direction in ("rise", "fall") and body.threshold > 100:
        raise HTTPException(422, "For rise/fall alerts the threshold is a percentage (1 to 100)")
    if body.notify_sms and sms.to_e164(user.phone) is None:
        raise HTTPException(422, "Your phone number looks invalid, so SMS alerts cannot be sent")
    alert = Alert(user_id=user.id, **body.model_dump())
    db.add(alert)
    db.commit()
    return _to_out(db, alert)


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(user: User = Depends(current_user), db: Session = Depends(get_db)):
    alerts = db.query(Alert).filter(Alert.user_id == user.id, Alert.active.is_(True)).all()
    return [_to_out(db, a) for a in alerts]


@router.delete("/alerts/{alert_id}")
def delete(alert_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if alert is None or alert.user_id != user.id:
        raise HTTPException(404, "Alert not found")
    alert.active = False
    db.commit()
    return {"ok": True}


# ---------- push registration and test ----------
@router.get("/push/public-key")
def public_key(_: User = Depends(current_user)):
    return {"public_key": settings.vapid_public_key or None}


@router.post("/push/subscribe")
def subscribe(body: PushSubscribeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    sub = db.query(PushSubscription).filter(PushSubscription.endpoint == body.endpoint).first()
    if sub is None:
        sub = PushSubscription(user_id=user.id, endpoint=body.endpoint, p256dh=body.keys.p256dh, auth=body.keys.auth)
        db.add(sub)
    else:  # same browser, maybe a different login: re-assign it
        sub.user_id, sub.p256dh, sub.auth = user.id, body.keys.p256dh, body.keys.auth
    db.commit()
    return {"ok": True}


@router.delete("/push/subscribe")
def unsubscribe(endpoint: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.query(PushSubscription).filter(PushSubscription.endpoint == endpoint, PushSubscription.user_id == user.id).delete()
    db.commit()
    return {"ok": True}


@router.post("/alerts/test")
def send_test(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Sends a test SMS and push to the logged-in user, to check the setup. Limited to 5 per hour."""
    recent = (db.query(AlertLog).filter(AlertLog.user_id == user.id, AlertLog.alert_id.is_(None),
                                        AlertLog.created_at >= utcnow() - timedelta(hours=1)).count())
    if recent >= 5:
        raise HTTPException(429, "Too many test messages. Try again later.")
    text = TEST_MESSAGE.get(user.language, TEST_MESSAGE["en"])
    sms_ok = sms.send_sms(user.phone, text)
    _log(db, None, user.id, "sms", sms_ok)
    n = push.send_push(db, user.id, "KrishiSense", text)
    if push.configured():
        _log(db, None, user.id, "push", n > 0)
    db.commit()
    return {"sms": sms_ok, "push_devices": n, "push_configured": push.configured(),
            "sms_provider": settings.sms_provider}
