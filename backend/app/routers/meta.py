from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Crop, Market
from ..schemas import CropOut, MarketOut

router = APIRouter(tags=["meta"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/crops", response_model=list[CropOut])
def crops(db: Session = Depends(get_db)):
    return db.query(Crop).order_by(Crop.name).all()


@router.get("/markets", response_model=list[MarketOut])
def markets(db: Session = Depends(get_db)):
    return db.query(Market).order_by(Market.name).all()
