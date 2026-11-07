"""Price forecasting helpers shared by the inference API (app.py) and training (train_price.py).

The model is a one-step-ahead gradient boosting regressor on the last LAGS prices, each
divided by their mean (so one model works for every crop/market). Multi-day forecasts are
made recursively. If no trained model exists, a damped-trend baseline is used instead.
"""
import math

import numpy as np

LAGS = 14


def make_features(window) -> tuple[np.ndarray, float]:
    w = np.asarray(window, dtype=float)
    scale = float(w.mean()) or 1.0
    x = w / scale
    feats = np.concatenate([x, [x[-1] - x[-7], x[-1] - x[0]]])
    return feats, scale


def _pad(prices, n=LAGS):
    prices = list(prices)
    if len(prices) < n:
        prices = [prices[0]] * (n - len(prices)) + prices
    return prices


def baseline_forecast(prices, horizon: int) -> dict:
    recent = list(prices)[-14:]
    slope = 0.5 * (recent[-1] - recent[0]) / max(len(recent) - 1, 1)
    diffs = [b - a for a, b in zip(recent, recent[1:])] or [0.0]
    mean = sum(diffs) / len(diffs)
    std = (sum((d - mean) ** 2 for d in diffs) / len(diffs)) ** 0.5
    pred, lo, hi, cum = [], [], [], 0.0
    for i in range(1, horizon + 1):
        cum += slope * (0.9 ** i)
        p = recent[-1] + cum
        spread = 1.28 * std * math.sqrt(i)
        pred.append(p), lo.append(p - spread), hi.append(p + spread)
    return {"predicted": pred, "lower": lo, "upper": hi, "method": "baseline"}


def model_forecast(bundle: dict, prices, horizon: int) -> dict:
    hist = _pad(prices)
    scale0 = float(np.mean(hist[-LAGS:])) or 1.0
    preds = []
    for _ in range(horizon):
        feats, scale = make_features(hist[-LAGS:])
        yhat = float(bundle["model"].predict([feats])[0]) * scale
        preds.append(yhat)
        hist.append(yhat)
    resid = float(bundle.get("resid_std", 0.03))
    lo = [p - 1.28 * resid * scale0 * math.sqrt(i + 1) for i, p in enumerate(preds)]
    hi = [p + 1.28 * resid * scale0 * math.sqrt(i + 1) for i, p in enumerate(preds)]
    return {"predicted": preds, "lower": lo, "upper": hi, "method": "ml"}
