from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import storage
from ..config import settings
from ..database import get_db
from ..deps import current_user
from ..models import Crop, Inquiry, Listing, User
from ..schemas import InquiryIn, InquiryOut, ListingOut, ListingUpdate
from ..services.pricing import latest_avg_price

router = APIRouter(tags=["marketplace"])
ALLOWED = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def _first_name(u: User) -> str:
    return (u.name or "Farmer").split()[0]


def _out(db: Session, l: Listing, me: User, cache: dict) -> ListingOut:
    seller = db.get(User, l.seller_id)
    crop = db.get(Crop, l.crop_id)
    if l.crop_id not in cache:
        cache[l.crop_id] = latest_avg_price(db, l.crop_id)
    mp = cache[l.crop_id]
    return ListingOut(id=l.id, crop_id=l.crop_id, crop=crop.name, title=l.title, description=l.description,
                      quantity_qtl=l.quantity_qtl, price_per_qtl=l.price_per_qtl, district=l.district,
                      state=l.state, image_url=storage.public_url(l.image_key), status=l.status,
                      seller_name=_first_name(seller), created_at=l.created_at, market_price=mp,
                      price_vs_market_pct=round((l.price_per_qtl - mp) / mp * 100, 1) if mp else None,
                      mine=l.seller_id == me.id)


@router.get("/market/fair-price")
def fair_price(crop_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    """Average latest mandi price across markets, to help a seller choose a fair asking price."""
    p = latest_avg_price(db, crop_id)
    return {"crop_id": crop_id, "market_price": p,
            "suggested_min": round(p * 0.95, 1) if p else None, "suggested_max": round(p * 1.10, 1) if p else None}


@router.post("/market/listings", response_model=ListingOut)
def create_listing(crop_id: int = Form(...), title: str = Form(..., min_length=3, max_length=120),
                   quantity_qtl: float = Form(..., gt=0), price_per_qtl: float = Form(..., gt=0),
                   description: str = Form("", max_length=1000), file: UploadFile | None = File(None),
                   user: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.get(Crop, crop_id) is None:
        raise HTTPException(404, "Unknown crop")
    key = None
    if file is not None and file.filename:
        if file.content_type not in ALLOWED:
            raise HTTPException(400, "Please upload a JPG, PNG or WEBP photo")
        limit = settings.max_upload_mb * 1024 * 1024
        data = file.file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, f"Photo is larger than {settings.max_upload_mb} MB")
        key = storage.save_image(user.id, data, ALLOWED[file.content_type], prefix="listings")
    l = Listing(seller_id=user.id, crop_id=crop_id, title=title, description=description,
                quantity_qtl=quantity_qtl, price_per_qtl=price_per_qtl, district=user.district,
                state=user.state, image_key=key)
    db.add(l)
    db.commit()
    return _out(db, l, user, {})


@router.get("/market/listings", response_model=list[ListingOut])
def browse(crop_id: int | None = None, district: str | None = None, q: str | None = None,
           max_price: float | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = db.query(Listing).filter(Listing.status == "active")
    if crop_id:
        query = query.filter(Listing.crop_id == crop_id)
    if district:
        query = query.filter(Listing.district == district)
    if max_price:
        query = query.filter(Listing.price_per_qtl <= max_price)
    if q:
        query = query.filter(Listing.title.ilike(f"%{q}%"))
    cache: dict = {}
    return [_out(db, l, user, cache) for l in query.order_by(Listing.created_at.desc()).limit(100).all()]


@router.get("/market/my-listings", response_model=list[ListingOut])
def mine(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = (db.query(Listing).filter(Listing.seller_id == user.id, Listing.status != "removed")
            .order_by(Listing.created_at.desc()).all())
    cache: dict = {}
    return [_out(db, l, user, cache) for l in rows]


def _own(db: Session, listing_id: int, user: User) -> Listing:
    l = db.get(Listing, listing_id)
    if l is None or l.seller_id != user.id or l.status == "removed":
        raise HTTPException(404, "Listing not found")
    return l


@router.patch("/market/listings/{listing_id}", response_model=ListingOut)
def update_listing(listing_id: int, body: ListingUpdate, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    l = _own(db, listing_id, user)
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(l, k, v)
    db.commit()
    return _out(db, l, user, {})


@router.delete("/market/listings/{listing_id}")
def remove_listing(listing_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _own(db, listing_id, user).status = "removed"
    db.commit()
    return {"ok": True}


@router.post("/market/listings/{listing_id}/inquire")
def inquire(listing_id: int, body: InquiryIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    l = db.get(Listing, listing_id)
    if l is None or l.status != "active":
        raise HTTPException(404, "Listing not found")
    if l.seller_id == user.id:
        raise HTTPException(400, "This is your own listing")
    if db.query(Inquiry).filter(Inquiry.listing_id == l.id, Inquiry.buyer_id == user.id).count() >= 3:
        raise HTTPException(429, "You already contacted this seller. Please wait for a reply.")
    db.add(Inquiry(listing_id=l.id, buyer_id=user.id, message=body.message))
    db.commit()
    return {"ok": True, "message": "Sent. The seller will call you on your registered number."}


@router.get("/market/inquiries", response_model=list[InquiryOut])
def my_inquiries(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Inquiries received on my listings. The buyer's phone is shared only with the seller."""
    rows = (db.query(Inquiry, Listing, User).join(Listing, Inquiry.listing_id == Listing.id)
            .join(User, Inquiry.buyer_id == User.id).filter(Listing.seller_id == user.id)
            .order_by(Inquiry.created_at.desc()).limit(100).all())
    return [InquiryOut(id=i.id, listing_id=l.id, listing_title=l.title, buyer_name=_first_name(b),
                       buyer_phone=b.phone, message=i.message, created_at=i.created_at) for i, l, b in rows]


@router.get("/media/{key:path}")
def media(key: str):
    """Serves marketplace photos only (never scan photos). With S3 enabled, photos use presigned URLs."""
    p = storage.local_path(key)
    if p is None:
        raise HTTPException(404, "Not found")
    return FileResponse(p, headers={"Cache-Control": "public, max-age=3600"})
