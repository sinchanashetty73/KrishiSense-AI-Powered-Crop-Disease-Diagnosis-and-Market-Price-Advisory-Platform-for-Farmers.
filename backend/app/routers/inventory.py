from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user
from ..models import Crop, InventoryItem, User, utcnow
from ..schemas import InventoryIn, InventoryOut, InventorySummary, InventoryUpdate
from ..services.pricing import latest_avg_price

router = APIRouter(prefix="/inventory", tags=["inventory"])
SELL_SOON_FRACTION = 0.7  # flag when 70% of the crop's shelf life has passed. TO CHANGE: edit here.


def _out(db: Session, it: InventoryItem, cache: dict) -> InventoryOut:
    crop = db.get(Crop, it.crop_id)
    if it.crop_id not in cache:
        cache[it.crop_id] = latest_avg_price(db, it.crop_id)
    price = cache[it.crop_id]
    days = max((utcnow().date() - it.harvest_date).days, 0)
    life = crop.shelf_life_days
    return InventoryOut(id=it.id, crop_id=it.crop_id, crop=crop.name, quantity_qtl=it.quantity_qtl,
                        harvest_date=it.harvest_date, storage_location=it.storage_location, notes=it.notes,
                        days_stored=days, shelf_life_days=life,
                        sell_soon=bool(life and it.quantity_qtl > 0 and days >= SELL_SOON_FRACTION * life),
                        market_price=price, est_value=round(price * it.quantity_qtl, 2) if price else None)


@router.get("", response_model=InventorySummary)
def list_items(user: User = Depends(current_user), db: Session = Depends(get_db)):
    items = db.query(InventoryItem).filter(InventoryItem.user_id == user.id).order_by(InventoryItem.harvest_date).all()
    cache: dict = {}
    out = [_out(db, i, cache) for i in items]
    return InventorySummary(items=out, total_qtl=round(sum(o.quantity_qtl for o in out), 2),
                            total_value=round(sum(o.est_value or 0 for o in out), 2),
                            sell_soon_count=sum(o.sell_soon for o in out))


@router.post("", response_model=InventoryOut)
def add_item(body: InventoryIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.get(Crop, body.crop_id) is None:
        raise HTTPException(404, "Unknown crop")
    if body.harvest_date > utcnow().date():
        raise HTTPException(422, "Harvest date cannot be in the future")
    it = InventoryItem(user_id=user.id, **body.model_dump())
    db.add(it)
    db.commit()
    return _out(db, it, {})


def _own(db: Session, item_id: int, user: User) -> InventoryItem:
    it = db.get(InventoryItem, item_id)
    if it is None or it.user_id != user.id:
        raise HTTPException(404, "Item not found")
    return it


@router.patch("/{item_id}", response_model=InventoryOut)
def update_item(item_id: int, body: InventoryUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    it = _own(db, item_id, user)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(it, k, v)
    db.commit()
    return _out(db, it, {})


@router.delete("/{item_id}")
def delete_item(item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(_own(db, item_id, user))
    db.commit()
    return {"ok": True}
