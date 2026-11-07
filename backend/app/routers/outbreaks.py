from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user
from ..models import Crop, Disease, Scan, User, utcnow
from ..schemas import OutbreakOut

router = APIRouter(tags=["outbreaks"])


@router.get("/outbreaks", response_model=list[OutbreakOut])
def outbreaks(days: int = 30, crop_id: int | None = None, district: str | None = None,
              _: User = Depends(current_user), db: Session = Depends(get_db)):
    """Aggregated, anonymised disease counts per district. Only counts and a coarse
    location (rounded to ~11 km) leave the server, never user ids or photos."""
    since = utcnow() - timedelta(days=days)
    q = (db.query(Scan.district, Crop.name, Disease.name, func.count(Scan.id),
                  func.avg(Scan.lat), func.avg(Scan.lon))
         .join(Disease, Scan.disease_id == Disease.id)
         .outerjoin(Crop, Disease.crop_id == Crop.id)
         .filter(Scan.created_at >= since, Scan.uncertain.is_(False),
                 Disease.is_healthy.is_(False), Scan.district.isnot(None)))
    if crop_id:
        q = q.filter(Disease.crop_id == crop_id)
    if district:
        q = q.filter(Scan.district == district)
    rows = q.group_by(Scan.district, Crop.name, Disease.name).order_by(func.count(Scan.id).desc()).all()
    return [OutbreakOut(district=d, crop=c, disease=dn, count=n,
                        lat=round(la, 1) if la is not None else None,
                        lon=round(lo, 1) if lo is not None else None)
            for d, c, dn, n, la, lo in rows]
