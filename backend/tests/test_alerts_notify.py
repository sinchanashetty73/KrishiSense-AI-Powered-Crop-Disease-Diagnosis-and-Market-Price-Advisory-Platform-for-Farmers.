import itertools
from datetime import date, timedelta

import pytest

from app.database import SessionLocal
from app.models import Alert, AlertLog, Crop, Market, MandiPrice, PushSubscription, User
from app.services import alert_dispatch, push, sms
from app.services.alerting import evaluate


_n = itertools.count()


@pytest.fixture()
def world(client, auth):
    """A private crop+market with a controlled price history: 100 three days ago, 120 today."""
    with SessionLocal() as db:
        db.query(Alert).update({Alert.active: False})  # isolate from alerts made by other tests
        n = next(_n)
        crop = Crop(name=f"TestArecanut{n}", shelf_life_days=300)
        market = Market(name=f"TestMandi{n}", state="Karnataka", district="Shivamogga", lat=13.9, lon=75.5)
        db.add_all([crop, market]); db.flush()
        today = date.today()
        db.add_all([MandiPrice(crop_id=crop.id, market_id=market.id, date=today - timedelta(days=3),
                               min_price=90, max_price=110, modal_price=100),
                    MandiPrice(crop_id=crop.id, market_id=market.id, date=today,
                               min_price=110, max_price=130, modal_price=120)])
        user = db.query(User).filter(User.phone == "9876543210").first()
        db.commit()
        ids = (crop.id, market.id, user.id)
    yield ids
    with SessionLocal() as db:  # leave the shared test database as we found it
        aids = [a.id for a in db.query(Alert).filter(Alert.crop_id == ids[0])]
        db.query(AlertLog).filter(AlertLog.alert_id.in_(aids)).delete(synchronize_session=False)
        db.query(Alert).filter(Alert.crop_id == ids[0]).delete()
        db.query(MandiPrice).filter(MandiPrice.crop_id == ids[0]).delete()
        db.query(Crop).filter(Crop.id == ids[0]).delete()
        db.query(Market).filter(Market.id == ids[1]).delete()
        db.commit()


def _alert(world, direction, threshold, **kw):
    c, m, u = world
    with SessionLocal() as db:
        a = Alert(user_id=u, crop_id=c, market_id=m, direction=direction, threshold=threshold, **kw)
        db.add(a); db.commit()
        return a.id


@pytest.mark.parametrize("direction,threshold,expected", [
    ("above", 110, True), ("above", 130, False), ("below", 130, True), ("below", 110, False),
    ("rise", 15, True), ("rise", 25, False), ("fall", 5, False)])
def test_evaluate(world, direction, threshold, expected):
    aid = _alert(world, direction, threshold)
    with SessionLocal() as db:
        ev = evaluate(db, db.get(Alert, aid))
    assert ev["triggered"] is expected and ev["change_pct"] == 20.0


def test_run_alerts_is_edge_triggered(world, monkeypatch):
    sent = []
    monkeypatch.setattr(sms, "send_sms", lambda phone, text: sent.append(text) or True)
    aid = _alert(world, "above", 110, notify_push=False)
    for _ in range(2):  # second run must not send again
        with SessionLocal() as db:
            alert_dispatch.run_alerts(db)
    assert sum("TestMandi" in t for t in sent) == 1
    # condition clears -> re-arms -> fires again when it becomes true
    with SessionLocal() as db:
        db.get(Alert, aid).threshold = 500; db.commit()
        alert_dispatch.run_alerts(db)
        assert db.get(Alert, aid).last_notified_at is None
        db.get(Alert, aid).threshold = 110; db.commit()
        alert_dispatch.run_alerts(db)
    assert sum("TestMandi" in t for t in sent) == 2


def test_failed_delivery_is_retried(world, monkeypatch):
    monkeypatch.setattr(sms, "send_sms", lambda phone, text: False)
    aid = _alert(world, "above", 110, notify_push=False)
    with SessionLocal() as db:
        alert_dispatch.run_alerts(db)
        assert db.get(Alert, aid).last_notified_at is None  # will retry next run
        assert db.query(AlertLog).filter(AlertLog.alert_id == aid, AlertLog.status == "failed").count() == 1


def test_messages_in_each_language():
    for lang in ("en", "hi", "kn"):
        for d in ("above", "below", "rise", "fall"):
            m = alert_dispatch.build_message(lang, d, "Arecanut", "Sirsi", 52000, 50000, 8.3)
            assert "Sirsi" in m or "Arecanut" in m


def test_phone_normalization():
    assert sms.to_e164("9876543210") == "+919876543210"
    assert sms.to_e164("+919876543210") == "+919876543210"
    assert sms.to_e164("919876543210") == "+919876543210"
    assert sms.to_e164("12345") is None


def test_sns_publish_arguments(monkeypatch):
    calls = {}

    class Fake:
        def publish(self, **kw): calls.update(kw)

    import boto3
    monkeypatch.setattr(boto3, "client", lambda *a, **k: Fake())
    monkeypatch.setattr(sms.settings, "sms_provider", "sns")
    monkeypatch.setattr(sms.settings, "sns_sender_id", "KRSENS")
    monkeypatch.setattr(sms.settings, "sns_entity_id", "E1")
    monkeypatch.setattr(sms.settings, "sns_template_id", "T1")
    assert sms.send_sms("9876543210", "hello") is True
    assert calls["PhoneNumber"] == "+919876543210"
    a = calls["MessageAttributes"]
    assert a["AWS.SNS.SMS.SMSType"]["StringValue"] == "Transactional"
    assert a["AWS.SNS.SMS.SenderID"]["StringValue"] == "KRSENS"
    assert a["AWS.MM.SMS.EntityId"]["StringValue"] == "E1" and a["AWS.MM.SMS.TemplateId"]["StringValue"] == "T1"


def test_sns_failure_does_not_raise(monkeypatch):
    import boto3

    class Boom:
        def publish(self, **kw): raise RuntimeError("sandbox")

    monkeypatch.setattr(boto3, "client", lambda *a, **k: Boom())
    monkeypatch.setattr(sms.settings, "sms_provider", "sns")
    assert sms.send_sms("9876543210", "x") is False


def test_push_subscription_and_dead_cleanup(client, auth, monkeypatch):
    body = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "k", "auth": "a"}}
    assert client.post("/api/push/subscribe", headers=auth, json=body).status_code == 200
    assert client.post("/api/push/subscribe", headers=auth, json=body).status_code == 200  # idempotent
    monkeypatch.setattr(push.settings, "vapid_public_key", "pub")
    monkeypatch.setattr(push.settings, "vapid_private_key", "priv")

    class Resp: status_code = 410
    def gone(**kw): raise push.WebPushException("gone", response=Resp())
    monkeypatch.setattr(push, "webpush", gone)
    with SessionLocal() as db:
        uid = db.query(User).filter(User.phone == "9876543210").first().id
        assert push.send_push(db, uid, "t", "b") == 0
        assert db.query(PushSubscription).filter(PushSubscription.endpoint == body["endpoint"]).count() == 0


def test_create_alert_validation_and_test_endpoint(client, auth, world):
    c, m, _ = world
    ok = client.post("/api/alerts", headers=auth, json={"crop_id": c, "market_id": m, "direction": "rise", "threshold": 10})
    assert ok.status_code == 200 and ok.json()["change_pct"] == 20.0 and ok.json()["triggered"] is True
    bad = client.post("/api/alerts", headers=auth, json={"crop_id": c, "market_id": m, "direction": "rise", "threshold": 500})
    assert bad.status_code == 422
    t = client.post("/api/alerts/test", headers=auth).json()
    assert t["sms"] is True and t["sms_provider"] == "log"
