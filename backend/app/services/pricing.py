from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from ..models import MandiPrice


def latest_avg_price(db: Session, crop_id: int) -> float | None:
    """Average of each market's most recent modal price (Rs per quintal) for a crop."""
    sub = (db.query(MandiPrice.market_id, func.max(MandiPrice.date).label("d"))
           .filter(MandiPrice.crop_id == crop_id).group_by(MandiPrice.market_id).subquery())
    rows = (db.query(MandiPrice.modal_price)
            .join(sub, and_(MandiPrice.market_id == sub.c.market_id, MandiPrice.date == sub.c.d))
            .filter(MandiPrice.crop_id == crop_id).all())
    prices = [r[0] for r in rows]
    return round(sum(prices) / len(prices), 1) if prices else None


def latest_by_market(db: Session, crop_id: int) -> list[tuple]:
    """[(Market, latest modal price, date)] for every market that has data for the crop."""
    from ..models import Market
    out = []
    for m in db.query(Market).all():
        last = (db.query(MandiPrice).filter(MandiPrice.crop_id == crop_id, MandiPrice.market_id == m.id)
                .order_by(MandiPrice.date.desc()).first())
        if last:
            out.append((m, last.modal_price, last.date))
    return out
