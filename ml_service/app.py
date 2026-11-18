"""ML inference service.

  POST /predict/disease   multipart image  -> top predictions (+ crop-level confidence)
  POST /forecast          {prices, horizon} -> price forecast
  GET  /health

Models are loaded from MODELS_DIR (default /models), in this order of preference:
  1. krishisense_v2.keras + class_names.json   <- trained in Colab (119 classes)
  2. disease.onnx + labels.json                <- old model
  3. DEMO MODE (fake but deterministic predictions, flagged "demo": true)
  price_model.joblib                           <- produced by train_price.py (retrain job)
"""
import hashlib
import io
import json
import os
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

import forecasting

MODELS_DIR = Path(os.getenv("MODELS_DIR", "/models"))
IMG_SIZE = 224
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)   # only used by the old ONNX model
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
DEMO_LABELS = ["Tomato___healthy", "Tomato___Early_blight", "Tomato___Late_blight",
               "Potato___Late_blight", "Pepper,_bell___Bacterial_spot"]
# fixes crop prefixes that differ between the training datasets
LABEL_ALIASES = {"Grapevine___Leafroll_disease": "Grape___Leafroll_disease"}

state: dict = {"keras": None, "session": None, "labels": None, "price": None}


def crop_of(label: str) -> str:
    return label.split("___")[0].replace("Grapevine", "Grape")


def load_models() -> None:
    state.update(keras=None, session=None, labels=None, price=None)
    keras_path, names_path = MODELS_DIR / "krishisense_v2.keras", MODELS_DIR / "class_names.json"
    onnx_path, labels_path = MODELS_DIR / "disease.onnx", MODELS_DIR / "labels.json"

    if keras_path.exists() and names_path.exists():
        import keras
        model = keras.saving.load_model(str(keras_path), compile=False)
        model(np.zeros((1, IMG_SIZE, IMG_SIZE, 3), dtype="float32"), training=False)  # warm-up
        state["keras"] = model
        state["labels"] = [LABEL_ALIASES.get(c, c) for c in json.loads(names_path.read_text())]
    elif onnx_path.exists() and labels_path.exists():
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


def load_image(data: bytes) -> Image.Image:
    try:
        return Image.open(io.BytesIO(data)).convert("RGB").resize((IMG_SIZE, IMG_SIZE))
    except (UnidentifiedImageError, OSError):
        raise HTTPException(400, "Not a valid image")


def preprocess_keras(img: Image.Image) -> np.ndarray:
    # the new model wants raw 0-255 pixels, shape (1, 224, 224, 3). Do NOT divide by 255.
    return np.asarray(img, dtype=np.float32)[None]


def preprocess_onnx(img: Image.Image) -> np.ndarray:
    arr = (np.asarray(img, dtype=np.float32) / 255.0 - MEAN) / STD
    return arr.transpose(2, 0, 1)[None].astype(np.float32)


def softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max())
    return e / e.sum()


@app.get("/health")
def health():
    backend = "keras" if state["keras"] is not None else "onnx" if state["session"] is not None else "demo"
    return {"status": "ok", "disease_backend": backend,
            "disease_model": backend != "demo", "price_model": state["price"] is not None}


@app.post("/predict/disease")
async def predict_disease(file: UploadFile = File(...)):
    data = await file.read()
    img = load_image(data)  # validates the image in all modes

    if state["keras"] is not None:
        probs = np.asarray(state["keras"](preprocess_keras(img), training=False))[0]  # already softmax
    elif state["session"] is not None:
        sess = state["session"]
        logits = sess.run(None, {sess.get_inputs()[0].name: preprocess_onnx(img)})[0][0]
        probs = softmax(logits)
    else:
        digest = int(hashlib.sha256(data).hexdigest(), 16)
        label = DEMO_LABELS[digest % len(DEMO_LABELS)]
        return {"label": label, "confidence": 0.85, "demo": True,
                "crop": crop_of(label), "crop_confidence": 0.85,
                "top": [{"label": label, "confidence": 0.85}]}

    labels = state["labels"]
    order = np.argsort(probs)[::-1][:3]
    top = [{"label": labels[i], "confidence": round(float(probs[i]), 4)} for i in order]

    # crop-level confidence: add up the probabilities of all diseases of the same crop
    crop_p: dict = defaultdict(float)
    for lab, p in zip(labels, probs):
        crop_p[crop_of(lab)] += float(p)
    crop, crop_conf = max(crop_p.items(), key=lambda kv: kv[1])

    return {"label": top[0]["label"], "confidence": top[0]["confidence"], "demo": False,
            "crop": crop, "crop_confidence": round(crop_conf, 4), "top": top}


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
    """Call after the retrain job writes a new model file (no container restart needed)."""
    load_models()
    return health()