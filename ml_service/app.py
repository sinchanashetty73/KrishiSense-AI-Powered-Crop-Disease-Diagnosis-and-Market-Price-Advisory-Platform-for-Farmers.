"""ML inference service.

  POST /predict/disease   multipart image  -> top predictions
  POST /forecast          {prices, horizon} -> price forecast
  GET  /health

Models are loaded from MODELS_DIR (default /models):
  disease.onnx + labels.json   <- produced by training/train_disease.py
  price_model.joblib           <- produced by train_price.py (retrain job)
If disease.onnx is missing the service runs in DEMO MODE (fake but deterministic predictions,
clearly flagged "demo": true) so you can test the whole app before training.
"""
import hashlib
import io
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

import forecasting

MODELS_DIR = Path(os.getenv("MODELS_DIR", "/models"))
IMG_SIZE = 224
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
DEMO_LABELS = ["Tomato___healthy", "Tomato___Early_blight", "Tomato___Late_blight",
               "Potato___Late_blight", "Pepper,_bell___Bacterial_spot"]

state: dict = {"session": None, "labels": None, "price": None}


def load_models() -> None:
    state.update(session=None, labels=None, price=None)
    onnx_path, labels_path = MODELS_DIR / "disease.onnx", MODELS_DIR / "labels.json"
    if onnx_path.exists() and labels_path.exists():
        import onnxruntime as ort
        state["session"] = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        state["labels"] = json.loads(labels_path.read_text())
    price_path = MODELS_DIR / "price_model.joblib"
    if price_path.exists():
        import joblib
        state["price"] = joblib.load(price_path)


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_models()
    yield


app = FastAPI(title="KrishiSense ML service", lifespan=lifespan)


def preprocess(data: bytes) -> np.ndarray:
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB").resize((IMG_SIZE, IMG_SIZE))
    except (UnidentifiedImageError, OSError):
        raise HTTPException(400, "Not a valid image")
    arr = (np.asarray(img, dtype=np.float32) / 255.0 - MEAN) / STD
    return arr.transpose(2, 0, 1)[None].astype(np.float32)


def softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max())
    return e / e.sum()


@app.get("/health")
def health():
    return {"status": "ok", "disease_model": state["session"] is not None,
            "price_model": state["price"] is not None}


@app.post("/predict/disease")
async def predict_disease(file: UploadFile = File(...)):
    data = await file.read()
    x = preprocess(data)  # validates the image in both modes
    if state["session"] is None:
        digest = int(hashlib.sha256(data).hexdigest(), 16)
        label = DEMO_LABELS[digest % len(DEMO_LABELS)]
        return {"label": label, "confidence": 0.85, "demo": True,
                "top": [{"label": label, "confidence": 0.85}]}
    sess = state["session"]
    logits = sess.run(None, {sess.get_inputs()[0].name: x})[0][0]
    probs = softmax(logits)
    order = np.argsort(probs)[::-1][:3]
    top = [{"label": state["labels"][i], "confidence": round(float(probs[i]), 4)} for i in order]
    return {"label": top[0]["label"], "confidence": top[0]["confidence"], "demo": False, "top": top}


class ForecastIn(BaseModel):
    prices: list[float] = Field(min_length=7, max_length=400)
    horizon: int = Field(default=7, ge=1, le=14)


@app.post("/forecast")
def forecast(body: ForecastIn):
    if state["price"] is not None:
        return forecasting.model_forecast(state["price"], body.prices, body.horizon)
    return forecasting.baseline_forecast(body.prices, body.horizon)


@app.post("/admin/reload")
def reload_models():
    """Call after the retrain job writes a new price_model.joblib (no container restart needed)."""
    load_models()
    return health()
