from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import ml_client, storage
from ..config import settings
from ..database import get_db
from ..deps import current_user
from ..models import Disease, Scan, User
from ..schemas import DiseaseOut, FeedbackIn, ScanHistoryItem, ScanOut, TopPrediction

router = APIRouter(prefix="/scans", tags=["scans"])
ALLOWED = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}

# General advice used when a class has no row in the Disease table yet.
# Order matters: the first group whose keyword appears in the label is used.
GENERAL_ADVICE = [
    (("healthy",),
     "The leaf looks healthy. Keep monitoring, water at the base of the plant and keep the field clean."),
    (("virus", "mosaic", "leafroll"),
     "This looks like a virus disease. Sprays do not cure viruses. Remove and destroy badly affected "
     "plants, control the insects that spread it (aphids, whiteflies, mealybugs, thrips) and use "
     "virus-free planting material."),
    (("bacterial", "fire_blight", "halo"),
     "This looks like a bacterial problem. Remove and destroy affected leaves or plants, avoid overhead "
     "watering, do not work in the field when plants are wet, and rotate crops. Use any chemical only "
     "on expert advice."),
    (("rust", "mildew", "blight", "spot", "scab", "rot", "mold", "mould", "anthracnose",
      "scorch", "measles", "esca", "smut", "frogeye"),
     "This looks like a fungal problem. Remove and destroy affected leaves, avoid wetting the leaves, "
     "give plants space for air flow, clean tools, and rotate crops. Ask your agriculture officer which "
     "fungicide, dose and timing suit your crop before spraying."),
]


def _general_advice(label: str) -> str:
    low = label.lower()
    for keys, text in GENERAL_ADVICE:
        if any(k in low for k in keys):
            return text
    return "Please confirm the problem and the right treatment with your local agriculture officer."


def _pretty(label: str) -> str:
    """'Grape___Leaf_spot' -> 'Leaf spot'"""
    return label.split("___")[-1].replace("_", " ")


def _crop_name(label: str) -> str:
    return label.split("___")[0].replace("Grapevine", "Grape")


def _crop_hint(pred: dict) -> str | None:
    """When the disease is unclear but the crop is clear, tell the farmer the crop and the candidates."""
    crop = pred.get("crop")
    if not crop or float(pred.get("crop_confidence") or 0) < 0.5:
        return None
    names = [_pretty(t["label"]) for t in pred.get("top", []) if _crop_name(t["label"]) == crop][:3]
    if not names:
        return None
    return (f"This looks like a {crop.replace('_', ' ')} leaf, but I'm not sure which problem it is. "
            f"Possible: {', '.join(names)}. Please confirm with your local agriculture officer, "
            "or retake the photo in daylight, close to a single affected leaf.")


@router.post("", response_model=ScanOut)
def create_scan(file: UploadFile = File(...), crop_id: int | None = Form(None),
                lat: float | None = Form(None), lon: float | None = Form(None),
                user: User = Depends(current_user), db: Session = Depends(get_db)):
    if file.content_type not in ALLOWED:
        raise HTTPException(400, "Please upload a JPG, PNG or WEBP image")
    limit = settings.max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"Image is larger than {settings.max_upload_mb} MB")
    if not data:
        raise HTTPException(400, "Empty file")

    try:
        pred = ml_client.predict_disease(data, file.filename or "leaf.jpg", file.content_type)
    except ml_client.MLUnavailable:
        raise HTTPException(503, "Disease detection is temporarily unavailable. Try again shortly.")

    label, conf = pred["label"], float(pred["confidence"])
    disease = db.query(Disease).filter(Disease.label == label).first()
    uncertain = conf < settings.confidence_threshold
    message = None
    if uncertain:
        message = _crop_hint(pred) or (
            "Not sure about this one. Retake the photo in daylight, close to a single "
            "affected leaf, with a plain background.")
    elif disease and crop_id and disease.crop_id and disease.crop_id != crop_id:
        uncertain = True
        message = "The leaf looks like a different crop than the one you selected. Please check and retry."
    elif disease is None:
        message = (f"Detected: {_pretty(label)} ({_crop_name(label).replace('_', ' ')}). "
                   f"{_general_advice(label)} This is automated advice, not a prescription. "
                   "Confirm with your local agriculture officer before applying chemicals.")

    key = storage.save_image(user.id, data, ALLOWED[file.content_type])
    scan = Scan(user_id=user.id, crop_id=crop_id or (disease.crop_id if disease else None),
                image_key=key, predicted_label=label, disease_id=disease.id if disease else None,
                confidence=conf, uncertain=uncertain, lat=lat, lon=lon, district=user.district)
    db.add(scan)
    db.commit()

    return ScanOut(
        id=scan.id, created_at=scan.created_at, label=label, confidence=conf,
        uncertain=uncertain, message=message, demo=bool(pred.get("demo")),
        disease=None if uncertain or disease is None else DiseaseOut.model_validate(disease),
        top=[TopPrediction(**t) for t in pred.get("top", [])])


@router.get("", response_model=list[ScanHistoryItem])
def history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return (db.query(Scan).filter(Scan.user_id == user.id)
            .order_by(Scan.created_at.desc()).limit(100).all())


@router.post("/{scan_id}/feedback")
def feedback(scan_id: int, body: FeedbackIn, user: User = Depends(current_user),
             db: Session = Depends(get_db)):
    scan = db.get(Scan, scan_id)
    if scan is None or scan.user_id != user.id:
        raise HTTPException(404, "Scan not found")
    scan.feedback = "correct" if body.correct else "wrong"
    scan.true_label = None if body.correct else body.true_label
    db.commit()
    return {"ok": True}