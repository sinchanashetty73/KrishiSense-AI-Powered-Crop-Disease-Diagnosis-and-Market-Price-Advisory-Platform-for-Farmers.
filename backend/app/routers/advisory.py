from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user
from ..models import Crop, Disease, User
from ..schemas import DiseaseBrief, DosageIn
from ..services import dosage, weather

router = APIRouter(tags=["advisory"])

DISCLAIMER = ("Doses are indicative. Always follow the product label and confirm chemical use with your "
              "local agriculture officer. Wear protective gear and keep children and animals away.")


@router.get("/advisory/spray")
def spray(lat: float | None = None, lon: float | None = None, user: User = Depends(current_user)):
    """Best spray windows for the next 48 hours from the weather forecast (rain, wind, heat)."""
    lat = lat if lat is not None else user.lat
    lon = lon if lon is not None else user.lon
    if lat is None or lon is None:
        raise HTTPException(422, "Save your location in Profile (or pass lat and lon) to get a spray advisory")
    try:
        return weather.spray_advisory(lat, lon)
    except weather.WeatherUnavailable:
        raise HTTPException(503, "Weather service is not reachable right now. Try again later.")


@router.get("/diseases", response_model=list[DiseaseBrief])
def diseases(_: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Disease, Crop.name).outerjoin(Crop, Disease.crop_id == Crop.id).order_by(Crop.name, Disease.name).all()
    return [DiseaseBrief(id=d.id, label=d.label, name=d.name, crop=c, is_healthy=d.is_healthy,
                         has_products=bool(d.products)) for d, c in rows]


@router.post("/dosage")
def calculate_dosage(body: DosageIn, _: User = Depends(current_user), db: Session = Depends(get_db)):
    d = db.get(Disease, body.disease_id)
    if d is None:
        raise HTTPException(404, "Unknown disease")
    if d.is_healthy or not d.products:
        raise HTTPException(422, "No spray products are listed for this condition. See the treatment advice.")
    out = dosage.calculate(d.products, body.area_acres, body.spray_volume_l_per_acre)
    return {"disease": d.name, **out, "disclaimer": DISCLAIMER}
