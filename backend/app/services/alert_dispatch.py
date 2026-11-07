"""Checks every active price alert and notifies farmers by SMS and/or push.

EDGE-TRIGGERED: a farmer is told once when the condition becomes true. The alert re-arms when the condition
stops being true, so a price that stays high does not send a message every run.
If every channel fails, the alert is NOT marked as notified, so the next run tries again.

Run it on a schedule (see docs/AWS_DEPLOYMENT.md, EventBridge Scheduler -> ECS RunTask):
    python -m app.jobs.run_alerts
Mandi prices update once a day, so run it right after the daily ingest job.
"""
import logging

from sqlalchemy.orm import Session

from ..models import Alert, AlertLog, Crop, Market, User, utcnow
from . import push, sms
from .alerting import CHANGE_WINDOW_DAYS, evaluate

log = logging.getLogger("krishisense.alerts")

# SMS wording. If you use India DLT, register templates with the same text and variables (the {} parts).
SMS_TEMPLATES = {
    "en": {
        "above": "KrishiSense: {crop} at {market} is Rs {price}/quintal, above your Rs {threshold}. Open the app to decide.",
        "below": "KrishiSense: {crop} at {market} is Rs {price}/quintal, below your Rs {threshold}. Open the app to decide.",
        "rise": "KrishiSense: {crop} at {market} is Rs {price}/quintal, up {change}% in {days} days. Open the app to decide.",
        "fall": "KrishiSense: {crop} at {market} is Rs {price}/quintal, down {change}% in {days} days. Open the app to decide.",
    },
    "hi": {
        "above": "कृषिसेंस: {market} में {crop} का भाव Rs {price}/क्विंटल, आपके Rs {threshold} से ऊपर। निर्णय के लिए ऐप खोलें।",
        "below": "कृषिसेंस: {market} में {crop} का भाव Rs {price}/क्विंटल, आपके Rs {threshold} से नीचे। निर्णय के लिए ऐप खोलें।",
        "rise": "कृषिसेंस: {market} में {crop} का भाव Rs {price}/क्विंटल, {days} दिन में {change}% बढ़ा। निर्णय के लिए ऐप खोलें।",
        "fall": "कृषिसेंस: {market} में {crop} का भाव Rs {price}/क्विंटल, {days} दिन में {change}% घटा। निर्णय के लिए ऐप खोलें।",
    },
    "kn": {
        "above": "ಕೃಷಿಸೆನ್ಸ್: {market} ನಲ್ಲಿ {crop} ಬೆಲೆ Rs {price}/ಕ್ವಿಂಟಾಲ್, ನಿಮ್ಮ Rs {threshold} ಕ್ಕಿಂತ ಹೆಚ್ಚು. ನಿರ್ಧರಿಸಲು ಆ್ಯಪ್ ತೆರೆಯಿರಿ.",
        "below": "ಕೃಷಿಸೆನ್ಸ್: {market} ನಲ್ಲಿ {crop} ಬೆಲೆ Rs {price}/ಕ್ವಿಂಟಾಲ್, ನಿಮ್ಮ Rs {threshold} ಕ್ಕಿಂತ ಕಡಿಮೆ. ನಿರ್ಧರಿಸಲು ಆ್ಯಪ್ ತೆರೆಯಿರಿ.",
        "rise": "ಕೃಷಿಸೆನ್ಸ್: {market} ನಲ್ಲಿ {crop} ಬೆಲೆ Rs {price}/ಕ್ವಿಂಟಾಲ್, {days} ದಿನದಲ್ಲಿ {change}% ಏರಿಕೆ. ನಿರ್ಧರಿಸಲು ಆ್ಯಪ್ ತೆರೆಯಿರಿ.",
        "fall": "ಕೃಷಿಸೆನ್ಸ್: {market} ನಲ್ಲಿ {crop} ಬೆಲೆ Rs {price}/ಕ್ವಿಂಟಾಲ್, {days} ದಿನದಲ್ಲಿ {change}% ಇಳಿಕೆ. ನಿರ್ಧರಿಸಲು ಆ್ಯಪ್ ತೆರೆಯಿರಿ.",
    },
}
TEST_MESSAGE = {"en": "KrishiSense: test notification. Your alerts are working.",
                "hi": "कृषिसेंस: परीक्षण संदेश। आपके अलर्ट काम कर रहे हैं।",
                "kn": "ಕೃಷಿಸೆನ್ಸ್: ಪರೀಕ್ಷಾ ಸಂದೇಶ. ನಿಮ್ಮ ಎಚ್ಚರಿಕೆಗಳು ಕೆಲಸ ಮಾಡುತ್ತಿವೆ."}


def build_message(lang: str, direction: str, crop: str, market: str, price: float, threshold: float,
                  change: float | None) -> str:
    tpl = SMS_TEMPLATES.get(lang, SMS_TEMPLATES["en"])[direction]
    return tpl.format(crop=crop, market=market, price=round(price), threshold=round(threshold),
                      change=abs(change) if change is not None else "", days=CHANGE_WINDOW_DAYS)


def _log(db: Session, alert_id: int | None, user_id: int, channel: str, ok: bool) -> None:
    db.add(AlertLog(alert_id=alert_id, user_id=user_id, channel=channel, status="sent" if ok else "failed"))


def run_alerts(db: Session) -> dict:
    stats = {"checked": 0, "triggered": 0, "notified": 0, "sms": 0, "push": 0, "failed": 0}
    for a in db.query(Alert).filter(Alert.active.is_(True)).all():
        stats["checked"] += 1
        ev = evaluate(db, a)
        if not ev["triggered"]:
            if a.last_notified_at is not None:
                a.last_notified_at = None  # re-arm for the next crossing
            continue
        stats["triggered"] += 1
        if a.last_notified_at is not None:
            continue  # farmer was already told about this crossing

        user, crop, market = db.get(User, a.user_id), db.get(Crop, a.crop_id), db.get(Market, a.market_id)
        text = build_message(user.language, a.direction, crop.name, market.name, ev["current_price"],
                             a.threshold, ev["change_pct"])
        delivered = False
        if a.notify_sms:
            ok = sms.send_sms(user.phone, text)
            _log(db, a.id, user.id, "sms", ok)
            stats["sms" if ok else "failed"] += 1
            delivered |= ok
        if a.notify_push:
            n = push.send_push(db, user.id, "KrishiSense", text, url="/")
            if push.configured():
                _log(db, a.id, user.id, "push", n > 0)
                stats["push" if n else "failed"] += 1
            delivered |= n > 0
        if delivered:
            a.last_notified_at = utcnow()
            stats["notified"] += 1
    db.commit()
    log.info("alert run: %s", stats)
    return stats
