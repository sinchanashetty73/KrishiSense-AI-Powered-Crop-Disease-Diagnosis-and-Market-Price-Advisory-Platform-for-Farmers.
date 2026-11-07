import importlib.util
import io
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app import ml_client
from app.services import weather

JPG = b"\xff\xd8\xff\xe0fakejpegbytes"


def register(client, phone, name):
    otp = client.post("/api/auth/request-otp", json={"phone": phone}).json()["dev_otp"]
    tok = client.post("/api/auth/verify-otp", json={"phone": phone, "code": otp, "name": name}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    client.patch("/api/me", json={"district": "Mysore", "state": "Karnataka"}, headers=h)
    return h


@pytest.fixture(scope="module")
def buyer(client):
    return register(client, "9111111111", "Ravi Kumar")


def _hours(start, n, over=None):
    rows = []
    for i in range(n):
        t = start + timedelta(hours=i)
        rows.append({"time": t, "temp": 26.0, "humidity": 60, "rain_prob": 5, "precip": 0.0, "wind": 6.0})
    for i, patch in (over or {}).items():
        rows[i].update(patch)
    return rows


# ---------- spray advisory (pure logic) ----------
def test_spray_windows_avoid_rain_and_night():
    start = datetime(2026, 10, 26, 0)
    hourly = _hours(start, 48, {13: {"rain_prob": 90}})
    adv = weather.compute_advisory(hourly, now=datetime(2026, 10, 26, 5, 30))
    assert adv["spray_now"] is False and "night" in adv["reasons"]
    w = adv["windows"][0]
    assert w["start"].endswith("06:00:00") and w["hours"] == 5 and w["end"].endswith("11:00:00")
    assert adv["windows"][1]["start"].endswith("14:00:00")


def test_spray_now_and_wind_block():
    hourly = _hours(datetime(2026, 10, 26, 0), 48)
    assert weather.compute_advisory(hourly, datetime(2026, 10, 26, 9, 10))["spray_now"] is True
    windy = _hours(datetime(2026, 10, 26, 0), 48, {9: {"wind": 30.0}})
    adv = weather.compute_advisory(windy, datetime(2026, 10, 26, 9, 10))
    assert adv["spray_now"] is False and "wind" in adv["reasons"]


def test_fungal_risk_flag():
    humid = _hours(datetime(2026, 10, 26, 0), 48, {i: {"humidity": 92, "temp": 22.0} for i in range(0, 8)})
    assert weather.compute_advisory(humid, datetime(2026, 10, 26, 0))["fungal_risk"] == "high"
    assert weather.compute_advisory(_hours(datetime(2026, 10, 26, 0), 48), datetime(2026, 10, 26, 0))["fungal_risk"] == "low"


def test_spray_endpoint(client, auth, monkeypatch):
    fake = {"spray_now": True, "reasons": [], "windows": [], "next_window": None, "fungal_risk": "low",
            "current": {"temp_c": 25, "wind_kmh": 5, "rain_prob": 0, "humidity": 50}, "rules": {}}
    monkeypatch.setattr(weather, "spray_advisory", lambda lat, lon: fake)
    assert client.get("/api/advisory/spray", headers=auth).json()["spray_now"] is True

    def down(lat, lon):
        raise weather.WeatherUnavailable("x")
    monkeypatch.setattr(weather, "spray_advisory", down)
    assert client.get("/api/advisory/spray", headers=auth).status_code == 503


def test_spray_needs_location(client):
    h = register(client, "9222222222", "No Location")
    assert client.get("/api/advisory/spray", headers=h).status_code == 422


# ---------- dosage ----------
def _disease_id(client, auth, name, crop):
    rows = client.get("/api/diseases", headers=auth).json()
    return next(d for d in rows if d["name"] == name and d["crop"] == crop)


def test_dosage_math(client, auth):
    d = _disease_id(client, auth, "Late blight", "Tomato")
    assert d["has_products"] is True
    r = client.post("/api/dosage", headers=auth, json={"disease_id": d["id"], "area_acres": 2}).json()
    assert r["water_litres"] == 400.0 and r["tanks"] == 25
    copper = next(p for p in r["products"] if p["name"].startswith("Copper"))
    assert copper["quantity"] == 1200.0 and copper["per_tank"] == 48.0  # 3 g/L
    r2 = client.post("/api/dosage", headers=auth, json={"disease_id": d["id"], "area_acres": 1,
                                                          "spray_volume_l_per_acre": 100}).json()
    assert r2["water_litres"] == 100.0
    assert "label" in r["disclaimer"]


def test_dosage_rejects_healthy_and_bad_input(client, auth):
    h = _disease_id(client, auth, "Healthy tomato leaf", "Tomato")
    assert client.post("/api/dosage", headers=auth, json={"disease_id": h["id"], "area_acres": 1}).status_code == 422
    d = _disease_id(client, auth, "Late blight", "Tomato")
    assert client.post("/api/dosage", headers=auth, json={"disease_id": d["id"], "area_acres": 0}).status_code == 422
    assert client.post("/api/dosage", headers=auth, json={"disease_id": 99999, "area_acres": 1}).status_code == 404


# ---------- chatbot ----------
def ask(client, h, msg, lang="en"):
    r = client.post("/api/chat", headers=h, json={"message": msg, "language": lang})
    assert r.status_code == 200, r.text
    return r.json()


def test_chat_price_three_languages(client, auth):
    en = ask(client, auth, "What is the tomato price?")
    assert en["intent"] == "price" and "Rs" in en["reply"] and "Tomato" in en["reply"]
    assert "₹" in ask(client, auth, "टमाटर का भाव", "hi")["reply"]
    assert "₹" in ask(client, auth, "ಟೊಮೇಟೊ ಬೆಲೆ", "kn")["reply"]
    assert ask(client, auth, "price?")["reply"].startswith("Which crop")


def test_chat_spray(client, auth, monkeypatch):
    adv = {"spray_now": False, "reasons": ["rain"], "next_window": {"start": "2026-10-26T06:00:00",
           "end": "2026-10-26T11:00:00"}, "fungal_risk": "high",
           "current": {"temp_c": 25, "wind_kmh": 5, "rain_prob": 80, "humidity": 90}}
    monkeypatch.setattr(weather, "spray_advisory", lambda lat, lon: adv)
    out = ask(client, auth, "when should I spray?")
    assert out["intent"] == "spray" and "rain likely" in out["reply"] and "06:00" in out["reply"] and "fungal" in out["reply"]


def test_chat_dosage_uses_last_scan(client, auth, monkeypatch):
    monkeypatch.setattr(ml_client, "predict_disease", lambda d, f, c: {
        "label": "Tomato___Late_blight", "confidence": 0.95, "demo": False, "top": []})
    client.post("/api/scans", headers=auth, files={"file": ("a.jpg", JPG, "image/jpeg")})
    out = ask(client, auth, "dose for 2 acres")
    assert out["intent"] == "dosage" and "400" in out["reply"] and "Late blight" in out["reply"]
    assert "acres" in ask(client, auth, "what dose should I use")["reply"]
    info = ask(client, auth, "treatment for late blight in potato")
    assert info["intent"] == "disease" and "Potato" in info["reply"]


def test_chat_fallback(client, auth):
    out = ask(client, auth, "hello there")
    assert out["intent"] == "help" and len(out["suggestions"]) == 4


# ---------- marketplace ----------
def test_marketplace_flow(client, auth, buyer):
    crop = next(c for c in client.get("/api/crops").json() if c["name"] == "Tomato")
    fp = client.get(f"/api/market/fair-price?crop_id={crop['id']}", headers=auth).json()
    assert fp["market_price"] and fp["suggested_min"] < fp["market_price"] < fp["suggested_max"]

    r = client.post("/api/market/listings", headers=auth,
                    data={"crop_id": crop["id"], "title": "Fresh red tomatoes", "quantity_qtl": 12,
                          "price_per_qtl": 2000, "description": "Grade A"},
                    files={"file": ("t.jpg", JPG, "image/jpeg")})
    assert r.status_code == 200, r.text
    lst = r.json()
    assert lst["mine"] is True and lst["seller_name"] == "Test" and lst["image_url"].startswith("/api/media/listings/")
    assert lst["price_vs_market_pct"] is not None

    # photo is served; private scan photos and path tricks are not
    assert client.get(lst["image_url"]).content == JPG
    assert client.get("/api/media/listings/../../etc/passwd").status_code == 404
    assert client.get("/api/media/scans/1/x.jpg").status_code == 404

    seen = client.get("/api/market/listings", headers=buyer).json()
    mine_in_buyer_view = next(x for x in seen if x["id"] == lst["id"])
    assert mine_in_buyer_view["mine"] is False
    assert "phone" not in str(mine_in_buyer_view).lower()

    assert client.post(f"/api/market/listings/{lst['id']}/inquire", headers=auth, json={"message": "hello there"}).status_code == 400
    ok = client.post(f"/api/market/listings/{lst['id']}/inquire", headers=buyer, json={"message": "Can you deliver to Mysuru?"})
    assert ok.status_code == 200
    inq = client.get("/api/market/inquiries", headers=auth).json()
    assert inq[0]["buyer_phone"] == "9111111111" and inq[0]["buyer_name"] == "Ravi"
    assert client.get("/api/market/inquiries", headers=buyer).json() == []

    assert client.patch(f"/api/market/listings/{lst['id']}", headers=buyer, json={"status": "sold"}).status_code == 404
    assert client.patch(f"/api/market/listings/{lst['id']}", headers=auth, json={"status": "sold"}).json()["status"] == "sold"
    assert all(x["id"] != lst["id"] for x in client.get("/api/market/listings", headers=buyer).json())
    assert client.post(f"/api/market/listings/{lst['id']}/inquire", headers=buyer, json={"message": "still there?"}).status_code == 404


def test_listing_validation(client, auth):
    crop = client.get("/api/crops").json()[0]["id"]
    bad = client.post("/api/market/listings", headers=auth, data={"crop_id": crop, "title": "x y z", "quantity_qtl": 1,
                      "price_per_qtl": 10}, files={"file": ("a.txt", b"hi", "text/plain")})
    assert bad.status_code == 400
    assert client.post("/api/market/listings", headers=auth, data={"crop_id": crop, "title": "ok title", "quantity_qtl": -1,
                       "price_per_qtl": 10}).status_code == 422


# ---------- inventory ----------
def test_inventory(client, auth, buyer):
    crops = {c["name"]: c["id"] for c in client.get("/api/crops").json()}
    today = datetime.utcnow().date()
    t = client.post("/api/inventory", headers=auth, json={"crop_id": crops["Tomato"], "quantity_qtl": 5,
                    "harvest_date": str(today - timedelta(days=9)), "storage_location": "Shed A"}).json()
    p = client.post("/api/inventory", headers=auth, json={"crop_id": crops["Potato"], "quantity_qtl": 20,
                    "harvest_date": str(today - timedelta(days=5))}).json()
    assert t["sell_soon"] is True and p["sell_soon"] is False and t["days_stored"] == 9
    assert t["est_value"] == round(t["market_price"] * 5, 2)

    s = client.get("/api/inventory", headers=auth).json()
    assert s["total_qtl"] == 25 and s["sell_soon_count"] == 1 and s["total_value"] > 0
    assert client.get("/api/inventory", headers=buyer).json()["items"] == []

    assert client.patch(f"/api/inventory/{t['id']}", headers=auth, json={"quantity_qtl": 2}).json()["quantity_qtl"] == 2
    assert client.patch(f"/api/inventory/{t['id']}", headers=buyer, json={"quantity_qtl": 1}).status_code == 404
    assert client.post("/api/inventory", headers=auth, json={"crop_id": crops["Tomato"], "quantity_qtl": 1,
                       "harvest_date": str(today + timedelta(days=2))}).status_code == 422
    assert "stock" in ask(client, auth, "my stock")["reply"]
    assert client.delete(f"/api/inventory/{p['id']}", headers=auth).status_code == 200


# ---------- ingestion pipeline (portable SQL) ----------
def test_ingest_upsert_is_idempotent(tmp_path):
    from sqlalchemy import create_engine, text

    from app.database import Base
    import app.models  # noqa: F401

    db_url = f"sqlite:///{tmp_path}/ing.db"
    eng = create_engine(db_url)
    Base.metadata.create_all(eng)
    with eng.begin() as c:
        c.execute(text("INSERT INTO crops(name, local_names) VALUES ('Tomato', '{}')"))

    path = Path(__file__).resolve().parents[2] / "pipelines" / "ingest_prices.py"
    spec = importlib.util.spec_from_file_location("ingest_prices", path)
    ing = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ing)

    day = datetime(2026, 10, 1).date()
    rows = [{"crop": "Tomato", "market": "Kolar", "district": "Kolar", "state": "Karnataka", "date": day,
             "min": 900.0, "max": 1300.0, "modal": 1100.0},
            {"crop": "Tomato", "market": "Hassan", "district": None, "state": None, "date": day,
             "min": 800.0, "max": 1000.0, "modal": 900.0}]
    assert ing.load(rows, db_url) == 2
    rows[0]["modal"] = 1150.0
    assert ing.load(rows, db_url) == 2  # second run updates, never duplicates
    with eng.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM mandi_prices")).scalar() == 2
        assert c.execute(text("SELECT COUNT(*) FROM markets")).scalar() == 2
        assert c.execute(text("SELECT modal_price FROM mandi_prices WHERE market_id=1")).scalar() == 1150.0
