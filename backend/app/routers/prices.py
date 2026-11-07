import math
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import ml_client
from ..database import get_db
from ..deps import current_user
from ..models import Crop, MandiPrice, Market, User
from ..schemas import (ForecastOut, ForecastPoint, MarketRank, PricePoint, ProfitIn, ProfitOut)

router = APIRouter(prefix="/prices", tags=["prices"])

ADVICE = {
    "wait": "Prices are likely to rise. Consider waiting a few days if you can store the crop safely.",
    "sell": "Prices are likely to fall. Consider selling soon.",
    "stable": "Prices look stable. Sell when it suits you.",
}


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def baseline_forecast(prices: list[float], horizon: int) -> dict:
    """Fallback used when the ML service is down: damped recent trend + spread from daily moves."""
    recent = prices[-14:]
    slope = 0.5 * (recent[-1] - recent[0]) / max(len(recent) - 1, 1)
    diffs = [b - a for a, b in zip(recent, recent[1:])] or [0.0]
    mean = sum(diffs) / len(diffs)
    std = (sum((x - mean) ** 2 for x in diffs) / len(diffs)) ** 0.5
    pred, lower, upper, cum = [], [], [], 0.0
    for i in range(1, horizon + 1):
        cum += slope * (0.9 ** i)
        p = recent[-1] + cum
        spread = 1.28 * std * math.sqrt(i)
        pred.append(p)
        lower.append(p - spread)
        upper.append(p + spread)
    return {"predicted": pred, "lower": lower, "upper": upper, "method": "baseline"}


def _crop_market(db: Session, crop_id: int, market_id: int) -> tuple[Crop, Market]:
    crop, market = db.get(Crop, crop_id), db.get(Market, market_id)
    if crop is None or market is None:
        raise HTTPException(404, "Unknown crop or market")
    return crop, market


@router.get("", response_model=list[PricePoint])
def history(crop_id: int, market_id: int, days: int = 60, _: User = Depends(current_user),
            db: Session = Depends(get_db)):
    days = max(1, min(days, 730))
    rows = (db.query(MandiPrice).filter(MandiPrice.crop_id == crop_id, MandiPrice.market_id == market_id)
            .order_by(MandiPrice.date.desc()).limit(days).all())
    return [PricePoint(date=r.date, modal_price=r.modal_price, min_price=r.min_price,
                       max_price=r.max_price) for r in reversed(rows)]


@router.get("/forecast", response_model=ForecastOut)
def forecast(crop_id: int, market_id: int, horizon: int = 7, _: User = Depends(current_user),
             db: Session = Depends(get_db)):
    horizon = max(1, min(horizon, 14))
    crop, market = _crop_market(db, crop_id, market_id)
    rows = (db.query(MandiPrice).filter(MandiPrice.crop_id == crop_id, MandiPrice.market_id == market_id)
            .order_by(MandiPrice.date.desc()).limit(90).all())
    if len(rows) < 7:
        raise HTTPException(422, "Not enough price history for a forecast yet")
    rows = list(reversed(rows))
    prices = [r.modal_price for r in rows]
    try:
        res = ml_client.forecast(prices, horizon)
    except ml_client.MLUnavailable:
        res = baseline_forecast(prices, horizon)
    last = prices[-1]
    avg = sum(res["predicted"]) / len(res["predicted"])
    change = (avg - last) / last * 100
    key = "wait" if change > 5 else "sell" if change < -5 else "stable"
    start = rows[-1].date
    points = [ForecastPoint(date=start + timedelta(days=i + 1), predicted=round(p, 1),
                            lower=round(lo, 1), upper=round(hi, 1))
              for i, (p, lo, hi) in enumerate(zip(res["predicted"], res["lower"], res["upper"]))]
    return ForecastOut(crop=crop.name, market=market.name, last_date=start, last_price=last,
                       method=res["method"], advice_key=key, advice=ADVICE[key],
                       change_pct=round(change, 1), points=points)


@router.get("/best-market", response_model=list[MarketRank])
def best_market(crop_id: int, lat: float | None = None, lon: float | None = None,
                cost_per_km: float = 2.0, user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    """Ranks markets by latest modal price minus transport cost (Rs per quintal per km).
    Uses the given lat/lon, else the user's saved location, else ignores distance."""
    lat = lat if lat is not None else user.lat
    lon = lon if lon is not None else user.lon
    out = []
    for m in db.query(Market).all():
        last = (db.query(MandiPrice).filter(MandiPrice.crop_id == crop_id, MandiPrice.market_id == m.id)
                .order_by(MandiPrice.date.desc()).first())
        if last is None:
            continue
        dist = cost = None
        net = last.modal_price
        if lat is not None and lon is not None and m.lat is not None and m.lon is not None:
            dist = round(haversine_km(lat, lon, m.lat, m.lon), 1)
            cost = round(dist * cost_per_km, 1)
            net = last.modal_price - cost
        out.append(MarketRank(market_id=m.id, market=m.name, district=m.district,
                              price=last.modal_price, price_date=last.date, distance_km=dist,
                              transport_cost=cost, net_price=round(net, 1)))
    return sorted(out, key=lambda r: r.net_price, reverse=True)


@router.post("/profit", response_model=ProfitOut)
def profit(body: ProfitIn, _: User = Depends(current_user)):
    revenue = body.quantity_qtl * body.price_per_qtl
    costs = body.transport_cost + body.other_costs
    return ProfitOut(revenue=round(revenue, 2), total_costs=round(costs, 2),
                     net_profit=round(revenue - costs, 2))
