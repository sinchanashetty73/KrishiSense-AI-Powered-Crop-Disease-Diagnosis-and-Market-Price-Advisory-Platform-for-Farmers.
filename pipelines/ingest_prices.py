"""Daily mandi price ingestion: API -> raw JSON (S3 or ./data/raw) -> validate -> upsert into MySQL.

Source: Agmarknet "Current daily price of various commodities from various markets (Mandi)"
on data.gov.in. You need a free API key from data.gov.in -> set DATA_GOV_API_KEY.

!! Verify RESOURCE_ID and the field names against the dataset page on data.gov.in before relying
!! on this: government APIs change. The code reads fields case-insensitively to tolerate that.

Run:  docker compose run --rm ingest            (or:  python ingest_prices.py --state Karnataka)
Schedule on AWS: EventBridge Scheduler -> ECS RunTask of this image (see docs/AWS_DEPLOYMENT.md).
"""
import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ingest")

RESOURCE_ID = os.getenv("DATA_GOV_RESOURCE_ID", "9ef84268-d588-465a-a308-a864a43d0070")
API_URL = f"https://api.data.gov.in/resource/{RESOURCE_ID}"
# API commodity name -> crop name in our `crops` table. TO CHANGE: add crops here and in backend/app/seed.py.
COMMODITIES = {"Tomato": "Tomato", "Potato": "Potato", "Maize": "Maize", "Capsicum": "Capsicum"}
MIN_RECORDS = int(os.getenv("MIN_RECORDS", "1"))


def fetch(api_key: str, state: str | None, limit: int = 500) -> list[dict]:
    records, offset = [], 0
    while True:
        params = {"api-key": api_key, "format": "json", "limit": limit, "offset": offset}
        if state:
            params["filters[state]"] = state
        for attempt in range(3):
            try:
                r = httpx.get(API_URL, params=params, timeout=60)
                r.raise_for_status()
                break
            except httpx.HTTPError as e:
                log.warning("fetch failed (attempt %d): %s", attempt + 1, e)
                if attempt == 2:
                    raise
        batch = r.json().get("records", [])
        records += batch
        if len(batch) < limit:
            return records
        offset += limit


def save_raw(records: list[dict]) -> str:
    key = f"raw/prices/{date.today():%Y/%m/%d}/prices-{datetime.now(timezone.utc):%H%M%S}.json"
    body = json.dumps(records).encode()
    bucket = os.getenv("S3_BUCKET")
    if bucket:
        import boto3
        boto3.client("s3", region_name=os.getenv("AWS_REGION", "ap-south-1")).put_object(
            Bucket=bucket, Key=key, Body=body)
    else:
        p = Path("data") / key
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
    return key


def clean(records: list[dict]) -> list[dict]:
    """Normalise field names, parse dates/numbers, drop bad rows (the data quality gate)."""
    out, dropped = [], 0
    for rec in records:
        r = {k.lower(): v for k, v in rec.items()}
        crop = COMMODITIES.get(str(r.get("commodity", "")).strip())
        try:
            d = datetime.strptime(str(r["arrival_date"]).strip(), "%d/%m/%Y").date()
            modal = float(r["modal_price"])
            lo, hi = float(r.get("min_price") or modal), float(r.get("max_price") or modal)
        except (KeyError, ValueError):
            dropped += 1
            continue
        if crop is None or not (0 < modal < 200_000) or lo > hi or d > date.today():
            dropped += 1
            continue
        out.append({"crop": crop, "market": str(r.get("market", "")).strip(),
                    "district": str(r.get("district", "")).strip() or None,
                    "state": str(r.get("state", "")).strip() or None,
                    "date": d, "min": lo, "max": hi, "modal": modal})
    log.info("kept %d rows, dropped %d bad/unwanted rows", len(out), dropped)
    return out


def _eq(col: str, val) -> str:
    return f"{col} IS NULL" if val is None else f"{col} = :{col}"


def _get_or_create_market(conn, name, district, state) -> int:
    params = {"name": name, "district": district, "state": state}
    mid = conn.execute(text(f"SELECT id FROM markets WHERE name = :name AND {_eq('district', district)} "
                            f"AND {_eq('state', state)}"), params).scalar()
    if mid is None:  # new market: lat/lon can be filled in later (best-market needs them)
        mid = conn.execute(text("INSERT INTO markets(name, district, state) VALUES (:name, :district, :state)"),
                           params).lastrowid
    return mid


def load(rows: list[dict], db_url: str) -> int:
    """Portable upsert (works on MySQL and SQLite): look the row up, then UPDATE or INSERT."""
    engine = create_engine(db_url)
    n, markets = 0, {}
    with engine.begin() as conn:
        crops = {r.name: r.id for r in conn.execute(text("SELECT id, name FROM crops"))}
        for r in rows:
            crop_id = crops.get(r["crop"])
            if crop_id is None or not r["market"]:
                continue
            key = (r["market"], r["district"], r["state"])
            if key not in markets:
                markets[key] = _get_or_create_market(conn, *key)
            p = {"mk": markets[key], "c": crop_id, "d": r["date"], "lo": r["min"], "hi": r["max"], "mo": r["modal"]}
            exists = conn.execute(text("SELECT id FROM mandi_prices WHERE market_id=:mk AND crop_id=:c AND date=:d"), p).scalar()
            if exists:
                conn.execute(text("UPDATE mandi_prices SET min_price=:lo, max_price=:hi, modal_price=:mo WHERE id=:id"),
                             {**p, "id": exists})
            else:
                conn.execute(text("INSERT INTO mandi_prices(market_id, crop_id, date, min_price, max_price, modal_price) "
                                  "VALUES (:mk, :c, :d, :lo, :hi, :mo)"), p)
            n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=os.getenv("INGEST_STATE", "Karnataka"))
    args = ap.parse_args()
    api_key, db_url = os.getenv("DATA_GOV_API_KEY"), os.getenv("DATABASE_URL")
    if not api_key or not db_url:
        log.error("Set DATA_GOV_API_KEY and DATABASE_URL")
        return 2
    records = fetch(api_key, args.state)
    log.info("fetched %d raw records", len(records))
    save_raw(records)
    rows = clean(records)
    if len(rows) < MIN_RECORDS:
        log.error("Only %d valid rows: source may be down or its format changed. Aborting.", len(rows))
        return 1
    log.info("upserted %d rows", load(rows, db_url))
    return 0


if __name__ == "__main__":
    sys.exit(main())
