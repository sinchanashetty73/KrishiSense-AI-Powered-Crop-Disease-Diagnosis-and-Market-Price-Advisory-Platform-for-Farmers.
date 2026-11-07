from app import ml_client


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_requires_auth(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/scans").status_code == 401


def test_bad_otp_rejected(client):
    client.post("/api/auth/request-otp", json={"phone": "9123456780"})
    r = client.post("/api/auth/verify-otp", json={"phone": "9123456780", "code": "000000"})
    assert r.status_code == 400


def test_invalid_phone_rejected(client):
    assert client.post("/api/auth/request-otp", json={"phone": "abc"}).status_code == 422


def test_profile(client, auth):
    me = client.get("/api/me", headers=auth).json()
    assert me["district"] == "Kolar" and me["name"] == "Test"


def test_crops_markets_seeded(client):
    assert len(client.get("/api/crops").json()) == 4
    assert len(client.get("/api/markets").json()) == 5


def _fake_predict(label, conf):
    def f(data, filename, content_type):
        return {"label": label, "confidence": conf, "demo": False,
                "top": [{"label": label, "confidence": conf}]}
    return f


def test_scan_confident(client, auth, monkeypatch):
    monkeypatch.setattr(ml_client, "predict_disease", _fake_predict("Tomato___Late_blight", 0.93))
    r = client.post("/api/scans", headers=auth, files={"file": ("a.jpg", b"fakejpg", "image/jpeg")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["uncertain"] is False and body["disease"]["name"] == "Late blight"
    fb = client.post(f"/api/scans/{body['id']}/feedback", headers=auth, json={"correct": True})
    assert fb.status_code == 200


def test_scan_low_confidence_is_uncertain(client, auth, monkeypatch):
    monkeypatch.setattr(ml_client, "predict_disease", _fake_predict("Tomato___Early_blight", 0.3))
    body = client.post("/api/scans", headers=auth, files={"file": ("a.png", b"x", "image/png")}).json()
    assert body["uncertain"] is True and body["disease"] is None and body["message"]


def test_scan_crop_mismatch_is_uncertain(client, auth, monkeypatch):
    monkeypatch.setattr(ml_client, "predict_disease", _fake_predict("Potato___Late_blight", 0.95))
    crops = {c["name"]: c["id"] for c in client.get("/api/crops").json()}
    body = client.post("/api/scans", headers=auth, data={"crop_id": crops["Tomato"]},
                       files={"file": ("a.jpg", b"x", "image/jpeg")}).json()
    assert body["uncertain"] is True


def test_scan_rejects_non_image(client, auth):
    r = client.post("/api/scans", headers=auth, files={"file": ("a.txt", b"hi", "text/plain")})
    assert r.status_code == 400


def test_scan_ml_down_returns_503(client, auth):
    r = client.post("/api/scans", headers=auth, files={"file": ("a.jpg", b"x", "image/jpeg")})
    assert r.status_code == 503


def test_scan_history_and_outbreaks(client, auth, monkeypatch):
    monkeypatch.setattr(ml_client, "predict_disease", _fake_predict("Tomato___Late_blight", 0.9))
    client.post("/api/scans", headers=auth, files={"file": ("a.jpg", b"x", "image/jpeg")})
    assert len(client.get("/api/scans", headers=auth).json()) >= 1
    out = client.get("/api/outbreaks", headers=auth).json()
    assert any(o["disease"] == "Late blight" and o["district"] == "Kolar" for o in out)
    assert all("user" not in o for o in out)


def _ids(client):
    crop = client.get("/api/crops").json()[0]["id"]
    market = client.get("/api/markets").json()[0]["id"]
    return crop, market


def test_price_history(client, auth):
    crop, market = _ids(client)
    rows = client.get(f"/api/prices?crop_id={crop}&market_id={market}&days=30", headers=auth).json()
    assert len(rows) == 30 and rows[0]["date"] < rows[-1]["date"]


def test_forecast_falls_back_to_baseline(client, auth):
    crop, market = _ids(client)
    r = client.get(f"/api/prices/forecast?crop_id={crop}&market_id={market}&horizon=7", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["method"] == "baseline" and len(body["points"]) == 7
    assert body["advice_key"] in ("wait", "sell", "stable")
    assert all(p["lower"] <= p["predicted"] <= p["upper"] for p in body["points"])


def test_forecast_uses_ml_when_available(client, auth, monkeypatch):
    crop, market = _ids(client)
    monkeypatch.setattr(ml_client, "forecast", lambda prices, h: {
        "predicted": [prices[-1] * 1.2] * h, "lower": [prices[-1]] * h,
        "upper": [prices[-1] * 1.4] * h, "method": "ml"})
    body = client.get(f"/api/prices/forecast?crop_id={crop}&market_id={market}", headers=auth).json()
    assert body["method"] == "ml" and body["advice_key"] == "wait"


def test_best_market_sorted_with_distance(client, auth):
    crop, _ = _ids(client)
    rows = client.get(f"/api/prices/best-market?crop_id={crop}", headers=auth).json()
    nets = [r["net_price"] for r in rows]
    assert nets == sorted(nets, reverse=True) and rows[0]["distance_km"] is not None


def test_profit(client, auth):
    r = client.post("/api/prices/profit", headers=auth, json={
        "quantity_qtl": 10, "price_per_qtl": 2000, "transport_cost": 500, "other_costs": 300})
    assert r.json() == {"revenue": 20000.0, "total_costs": 800.0, "net_profit": 19200.0}


def test_alert_lifecycle(client, auth):
    crop, market = _ids(client)
    a = client.post("/api/alerts", headers=auth, json={
        "crop_id": crop, "market_id": market, "direction": "above", "threshold": 1}).json()
    assert a["triggered"] is True
    b = client.post("/api/alerts", headers=auth, json={
        "crop_id": crop, "market_id": market, "direction": "above", "threshold": 10_000_000}).json()
    assert b["triggered"] is False
    assert client.delete(f"/api/alerts/{a['id']}", headers=auth).status_code == 200
    ids = [x["id"] for x in client.get("/api/alerts", headers=auth).json()]
    assert a["id"] not in ids and b["id"] in ids
