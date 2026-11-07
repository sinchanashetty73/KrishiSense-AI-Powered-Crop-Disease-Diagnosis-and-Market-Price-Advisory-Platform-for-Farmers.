import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["UPLOAD_DIR"] = f"{_tmp}/uploads"
os.environ["ML_SERVICE_URL"] = "http://127.0.0.1:9"  # nothing listens here -> tests the fallback path
os.environ["DEV_OTP_ECHO"] = "true"
os.environ["S3_BUCKET"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth(client):
    phone = "9876543210"
    otp = client.post("/api/auth/request-otp", json={"phone": phone}).json()["dev_otp"]
    token = client.post("/api/auth/verify-otp", json={"phone": phone, "code": otp, "name": "Test"}).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    client.patch("/api/me", json={"district": "Kolar", "state": "Karnataka", "lat": 13.1, "lon": 78.1}, headers=h)
    return h
