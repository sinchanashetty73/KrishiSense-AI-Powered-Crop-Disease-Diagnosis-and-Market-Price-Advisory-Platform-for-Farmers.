"""Weather-based spray advisory.

Uses the free Open-Meteo forecast API (no API key). The decision logic (compute_advisory) is a pure
function so it can be tested without network access.

!! Verify the Open-Meteo parameter names against https://open-meteo.com/en/docs if the API changes.

RULES (typical extension guidance, adjust in the constants below and have an agronomist review):
  * Do not spray in wind above MAX_WIND_KMH (drift, uneven coverage).
  * Do not spray if rain is likely (probability above MAX_RAIN_PROB or any rain) in that hour or the
    next RAIN_FREE_HOURS hours (the product needs time to dry / be absorbed).
  * Avoid heat above MAX_TEMP_C (leaf burn, fast evaporation).
  * Only daytime hours DAY_START..DAY_END are suggested.
"""
import time
from datetime import datetime, timedelta, timezone

import httpx

MAX_WIND_KMH = 15.0
MAX_RAIN_PROB = 30
MAX_TEMP_C = 32.0
RAIN_FREE_HOURS = 2          # this hour and the next 2 must be dry
DAY_START, DAY_END = 6, 19   # suggest windows between 06:00 and 19:00
MIN_WINDOW_HOURS = 2
FUNGAL_HUMIDITY = 85
FUNGAL_TEMP = (18.0, 28.0)
FUNGAL_HOURS = 6

API_URL = "https://api.open-meteo.com/v1/forecast"
_cache: dict = {}


class WeatherUnavailable(Exception):
    pass


def fetch_hourly(lat: float, lon: float) -> tuple[list[dict], int]:
    """Returns (hourly rows in the farm's local time, UTC offset in seconds)."""
    key = (round(lat, 2), round(lon, 2))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < 1800:
        return hit[1]
    params = {"latitude": lat, "longitude": lon, "forecast_days": 2, "timezone": "auto",
              "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,wind_speed_10m"}
    try:
        r = httpx.get(API_URL, params=params, timeout=10)
        r.raise_for_status()
        body = r.json()
        h, offset = body["hourly"], int(body.get("utc_offset_seconds", 19800))
        rows = [{"time": datetime.fromisoformat(t), "temp": h["temperature_2m"][i],
                 "humidity": h["relative_humidity_2m"][i], "rain_prob": h["precipitation_probability"][i] or 0,
                 "precip": h["precipitation"][i] or 0, "wind": h["wind_speed_10m"][i]}
                for i, t in enumerate(h["time"])]
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as e:
        raise WeatherUnavailable(str(e)) from e
    _cache[key] = (time.time(), (rows, offset))
    return rows, offset


def _ok(h: dict) -> bool:
    return (h["wind"] is not None and h["wind"] <= MAX_WIND_KMH and h["rain_prob"] <= MAX_RAIN_PROB
            and h["precip"] == 0 and h["temp"] is not None and h["temp"] <= MAX_TEMP_C)


def compute_advisory(hourly: list[dict], now: datetime) -> dict:
    hours = [h for h in hourly if h["time"] >= now.replace(minute=0, second=0, microsecond=0)]
    good = []
    for i, h in enumerate(hours):
        window = hours[i:i + RAIN_FREE_HOURS + 1]
        good.append(DAY_START <= h["time"].hour < DAY_END and len(window) == RAIN_FREE_HOURS + 1
                    and all(_ok(x) for x in window))

    windows, start = [], None
    for i, g in enumerate(good + [False]):
        if g and start is None:
            start = i
        elif not g and start is not None:
            if i - start >= MIN_WINDOW_HOURS:
                seg = hours[start:i]
                windows.append({"start": seg[0]["time"].isoformat(), "end": (seg[-1]["time"] + timedelta(hours=1)).isoformat(), "hours": i - start,
                    "avg_wind_kmh": round(sum(x["wind"] for x in seg) / len(seg), 1),
                    "avg_temp_c": round(sum(x["temp"] for x in seg) / len(seg), 1)})
            start = None

    spray_now = bool(good and good[0])
    reasons = []
    if hours:
        h0 = hours[0]
        if h0["wind"] > MAX_WIND_KMH:
            reasons.append("wind")
        if h0["rain_prob"] > MAX_RAIN_PROB or h0["precip"] > 0 or any(
                x["rain_prob"] > MAX_RAIN_PROB or x["precip"] > 0 for x in hours[1:RAIN_FREE_HOURS + 1]):
            reasons.append("rain")
        if h0["temp"] > MAX_TEMP_C:
            reasons.append("heat")
        if not (DAY_START <= h0["time"].hour < DAY_END):
            reasons.append("night")

    run = best = 0
    for h in hours[:48]:
        hit = h["humidity"] >= FUNGAL_HUMIDITY and FUNGAL_TEMP[0] <= h["temp"] <= FUNGAL_TEMP[1]
        run = run + 1 if hit else 0
        best = max(best, run)
    fungal_risk = "high" if best >= FUNGAL_HOURS else "low"

    return {"spray_now": spray_now, "reasons": [] if spray_now else reasons, "windows": windows[:4],
            "next_window": windows[0] if windows else None, "fungal_risk": fungal_risk,
            "current": {"temp_c": hours[0]["temp"], "wind_kmh": hours[0]["wind"],
                        "rain_prob": hours[0]["rain_prob"], "humidity": hours[0]["humidity"]} if hours else None,
            "rules": {"max_wind_kmh": MAX_WIND_KMH, "max_rain_prob": MAX_RAIN_PROB, "max_temp_c": MAX_TEMP_C,
                      "rain_free_hours": RAIN_FREE_HOURS}}


def spray_advisory(lat: float, lon: float) -> dict:
    rows, offset = fetch_hourly(lat, lon)
    now = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=offset)
    return compute_advisory(rows, now)
