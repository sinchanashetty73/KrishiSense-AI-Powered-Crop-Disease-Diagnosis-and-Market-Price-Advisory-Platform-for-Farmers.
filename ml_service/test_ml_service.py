import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

_tmp = tempfile.mkdtemp()
os.environ["MODELS_DIR"] = _tmp

from fastapi.testclient import TestClient  # noqa: E402

import app as ml  # noqa: E402


def _png() -> bytes:
    buf = io.BytesIO()
    Image.fromarray(np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)).save(buf, "PNG")
    return buf.getvalue()


def test_demo_mode_and_validation():
    with TestClient(ml.app) as c:
        h = c.get("/health").json()
        assert h["disease_model"] is False
        data = _png()
        r1 = c.post("/predict/disease", files={"file": ("a.png", data, "image/png")}).json()
        r2 = c.post("/predict/disease", files={"file": ("a.png", data, "image/png")}).json()
        assert r1["demo"] is True and r1 == r2  # deterministic
        bad = c.post("/predict/disease", files={"file": ("a.png", b"notimage", "image/png")})
        assert bad.status_code == 400


def test_baseline_forecast_shapes():
    with TestClient(ml.app) as c:
        r = c.post("/forecast", json={"prices": [100 + i for i in range(30)], "horizon": 5}).json()
        assert r["method"] == "baseline" and len(r["predicted"]) == 5
        assert r["predicted"][0] > 129  # follows the upward trend
        assert c.post("/forecast", json={"prices": [1, 2], "horizon": 5}).status_code == 422


def test_train_price_and_serve():
    rng = np.random.default_rng(0)
    rows = []
    for market in (1, 2):
        base = 1500 + 200 * market
        for i in range(260):
            d = pd.Timestamp("2025-01-01") + pd.Timedelta(days=i)
            price = base * (1 + 0.2 * np.sin(2 * np.pi * i / 60)) + rng.normal(0, 8)
            rows.append({"crop_id": 1, "market_id": market, "date": d, "modal_price": price})
    csv = Path(_tmp) / "p.csv"
    pd.DataFrame(rows).to_csv(csv, index=False)
    out = subprocess.run([sys.executable, "train_price.py", "--csv", str(csv), "--out", _tmp],
                         capture_output=True, text=True, cwd=Path(__file__).parent)
    assert out.returncode == 0, out.stderr
    assert "Promoted" in out.stdout, out.stdout
    with TestClient(ml.app) as c:  # lifespan reloads models from MODELS_DIR
        assert c.get("/health").json()["price_model"] is True
        prices = [r["modal_price"] for r in rows[:100]]
        r = c.post("/forecast", json={"prices": prices, "horizon": 7}).json()
        assert r["method"] == "ml" and len(r["predicted"]) == 7
        assert all(lo <= p <= hi for lo, p, hi in zip(r["lower"], r["predicted"], r["upper"]))
