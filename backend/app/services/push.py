"""Browser / phone push notifications using the Web Push standard (VAPID). No third-party account needed.
Works in Chrome/Edge/Firefox on Android and desktop. On iPhone (iOS 16.4+) the app must be added to the home screen.
Push needs HTTPS (http://localhost is allowed for development). Generate keys: python scripts/generate_vapid.py
"""
import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy.orm import Session

from ..config import settings
from ..models import PushSubscription

log = logging.getLogger("krishisense.push")


def configured() -> bool:
    return bool(settings.vapid_public_key and settings.vapid_private_key)


def send_push(db: Session, user_id: int, title: str, body: str, url: str = "/") -> int:
    """Sends to every registered device of the user. Returns how many succeeded. Dead subscriptions are removed."""
    if not configured():
        return 0
    sent = 0
    payload = json.dumps({"title": title, "body": body, "url": url})
    for sub in db.query(PushSubscription).filter(PushSubscription.user_id == user_id).all():
        try:
            webpush(subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
                    data=payload, vapid_private_key=settings.vapid_private_key,
                    vapid_claims={"sub": settings.vapid_subject}, ttl=86400)
            sent += 1
        except WebPushException as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (404, 410):  # the browser unsubscribed: forget it
                db.delete(sub)
            else:
                log.warning("Push failed (%s): %s", status, e)
        except Exception as e:
            log.warning("Push failed: %s", e)
    db.commit()
    return sent
