"""Train / retrain the price forecaster from the mandi_prices table (or a CSV).

Usage (inside docker compose):  docker compose run --rm retrain
Usage (local):  python train_price.py --db-url mysql+pymysql://ks:pw@localhost:3306/krishisense --out ../models
                python train_price.py --csv prices.csv --out ../models     (cols: crop_id,market_id,date,modal_price)

Evaluation is walk-forward: train on the first 80% of dates, test on the last 20%, and compare
the 7-day-ahead error with a naive "tomorrow = today" baseline. The new model is saved only
if it beats the naive baseline AND the model already deployed (if any).
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from forecasting import LAGS, make_features, model_forecast

HORIZON = 7


def load_df(args) -> pd.DataFrame:
    if args.csv:
        df = pd.read_csv(args.csv)
    else:
        from sqlalchemy import create_engine
        df = pd.read_sql("SELECT crop_id, market_id, date, modal_price FROM mandi_prices",
                         create_engine(args.db_url))
    df["date"] = pd.to_datetime(df["date"])
    return df


def build_series(df: pd.DataFrame) -> list[pd.Series]:
    out = []
    for _, g in df.groupby(["crop_id", "market_id"]):
        s = g.groupby("date")["modal_price"].mean().sort_index().asfreq("D").ffill()
        if len(s) >= LAGS + 40:
            out.append(s)
    return out


def samples(series: list[pd.Series], start=None, end=None):
    X, y = [], []
    for s in series:
        v, idx = s.values, s.index
        for t in range(LAGS, len(v)):
            if (start is not None and idx[t] < start) or (end is not None and idx[t] >= end):
                continue
            feats, scale = make_features(v[t - LAGS:t])
            X.append(feats)
            y.append(v[t] / scale)
    return np.array(X), np.array(y)


def new_model():
    return HistGradientBoostingRegressor(max_depth=4, learning_rate=0.06, max_iter=300, random_state=0)


def horizon_mape(bundle, series, cutoff, stride=3):
    model_err, naive_err = [], []
    for s in series:
        v, idx = s.values, s.index
        for t in range(LAGS, len(v) - HORIZON, stride):
            if idx[t] < cutoff:
                continue
            actual = v[t + HORIZON - 1]
            pred = model_forecast(bundle, v[:t], HORIZON)["predicted"][-1]
            model_err.append(abs(pred - actual) / actual)
            naive_err.append(abs(v[t - 1] - actual) / actual)
    return float(np.mean(model_err)), float(np.mean(naive_err))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-url")
    ap.add_argument("--csv")
    ap.add_argument("--out", default="/models")
    args = ap.parse_args()
    if not (args.db_url or args.csv):
        import os
        args.db_url = os.getenv("DATABASE_URL")
    if not (args.db_url or args.csv):
        ap.error("give --db-url, --csv or set DATABASE_URL")

    series = build_series(load_df(args))
    if not series:
        print("Not enough history yet (need >= %d days per crop/market)." % (LAGS + 40))
        return 1
    all_dates = sorted({d for s in series for d in s.index})
    cutoff = all_dates[int(len(all_dates) * 0.8)]

    X_tr, y_tr = samples(series, end=cutoff)
    X_te, y_te = samples(series, start=cutoff)
    model = new_model().fit(X_tr, y_tr)
    resid_std = float(np.std(y_te - model.predict(X_te)))
    bundle = {"model": model, "resid_std": resid_std}
    m_mape, n_mape = horizon_mape(bundle, series, cutoff)
    metrics = {"trained_at": datetime.now(timezone.utc).isoformat(), "series": len(series),
               "train_rows": int(len(y_tr)), "test_rows": int(len(y_te)),
               f"model_mape_{HORIZON}d": round(m_mape, 4), f"naive_mape_{HORIZON}d": round(n_mape, 4),
               "resid_std": round(resid_std, 4)}
    print(json.dumps(metrics, indent=2))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    metrics_path, model_path = out / "price_metrics.json", out / "price_model.joblib"
    if m_mape >= n_mape:
        print("Model does not beat the naive baseline: NOT promoting it.")
        return 0
    if metrics_path.exists():
        old = json.loads(metrics_path.read_text()).get(f"model_mape_{HORIZON}d")
        if old is not None and m_mape >= old and model_path.exists():
            print("Model is not better than the one already deployed: NOT promoting it.")
            return 0
    # Promote: refit on ALL data so the deployed model has seen the latest prices.
    X_all, y_all = samples(series)
    final = new_model().fit(X_all, y_all)
    joblib.dump({"model": final, "resid_std": resid_std, "lags": LAGS, "metrics": metrics}, model_path)
    metrics_path.write_text(json.dumps(metrics, indent=2))
    print("Promoted new price model ->", model_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
