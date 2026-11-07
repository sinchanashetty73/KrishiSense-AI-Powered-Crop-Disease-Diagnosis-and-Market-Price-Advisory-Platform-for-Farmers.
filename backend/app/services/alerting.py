"""Decides whether a price alert is currently true.

Directions:
  above / below : modal price in Rs per quintal at the chosen market crosses the threshold
  rise  / fall  : percent change versus CHANGE_WINDOW_DAYS days earlier reaches the threshold
"""
from datetime import timedelta

from sqlalchemy.orm import Session

from ..models import Alert, MandiPrice

CHANGE_WINDOW_DAYS = 3  # TO CHANGE: window used by "rise" / "fall" alerts


def evaluate(db: Session, a: Alert) -> dict:
    q = db.query(MandiPrice).filter(MandiPrice.crop_id == a.crop_id, MandiPrice.market_id == a.market_id)
    last = q.order_by(MandiPrice.date.desc()).first()
    if last is None:
        return {"triggered": False, "current_price": None, "change_pct": None, "date": None}
    price = last.modal_price
    change = None
    past = (q.filter(MandiPrice.date <= last.date - timedelta(days=CHANGE_WINDOW_DAYS))
            .order_by(MandiPrice.date.desc()).first())
    if past and past.modal_price:
        change = round((price - past.modal_price) / past.modal_price * 100, 1)

    if a.direction == "above":
        hit = price >= a.threshold
    elif a.direction == "below":
        hit = price <= a.threshold
    elif a.direction == "rise":
        hit = change is not None and change >= a.threshold
    else:  # fall
        hit = change is not None and -change >= a.threshold
    return {"triggered": hit, "current_price": price, "change_pct": change, "date": last.date}
