"""Thin HTTP client for the separate ML service (ml_service/)."""
import httpx

from .config import settings


class MLUnavailable(Exception):
    pass


def predict_disease(data: bytes, filename: str, content_type: str) -> dict:
    try:
        r = httpx.post(f"{settings.ml_service_url}/predict/disease",
                       files={"file": (filename, data, content_type)}, timeout=30)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        raise MLUnavailable(str(e)) from e


def forecast(prices: list[float], horizon: int) -> dict:
    try:
        r = httpx.post(f"{settings.ml_service_url}/forecast",
                       json={"prices": prices, "horizon": horizon}, timeout=10)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        raise MLUnavailable(str(e)) from e
