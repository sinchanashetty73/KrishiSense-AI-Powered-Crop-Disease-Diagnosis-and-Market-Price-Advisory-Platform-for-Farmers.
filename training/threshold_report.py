"""Pick a confidence threshold from data. Runs the held-out test photos through the trained model and prints,
for each threshold, how many photos get an answer and how often that answer is right.

  python threshold_report.py --models ..\\models --test data\\field_test

Needs: pip install onnxruntime pillow numpy   (ml_service/requirements.txt already has them)
"""
import argparse
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def softmax(x):
    e = np.exp(x - x.max())
    return e / e.sum()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True, help="folder with disease.onnx and labels.json")
    ap.add_argument("--test", required=True, help="folder of class sub-folders (the held-out field_test)")
    ap.add_argument("--max-per-class", type=int, default=0, help="limit images per class (0 = all)")
    args = ap.parse_args()

    models = Path(args.models)
    labels = json.loads((models / "labels.json").read_text())
    idx = {n: i for i, n in enumerate(labels)}
    sess = ort.InferenceSession(str(models / "disease.onnx"), providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name

    rows = []  # (confidence, correct)
    for cls_dir in sorted(p for p in Path(args.test).iterdir() if p.is_dir()):
        if cls_dir.name not in idx:
            continue
        files = sorted(f for f in cls_dir.iterdir() if f.suffix.lower() in EXT)
        if args.max_per_class:
            files = files[:args.max_per_class]
        for f in files:
            a = (np.asarray(Image.open(f).convert("RGB").resize((224, 224)), dtype=np.float32) / 255.0 - MEAN) / STD
            p = softmax(sess.run(None, {name: a.transpose(2, 0, 1)[None].astype(np.float32)})[0][0])
            rows.append((float(p.max()), int(p.argmax()) == idx[cls_dir.name]))
    if not rows:
        raise SystemExit("No test images found. Check --test and that class folder names match labels.json.")

    conf = np.array([r[0] for r in rows])
    ok = np.array([r[1] for r in rows])
    print(f"{len(rows)} test photos. Accuracy if every photo gets an answer: {ok.mean():.1%}\n")
    print("threshold | photos answered | accuracy of answers given")
    for t in (0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80):
        m = conf >= t
        acc = f"{ok[m].mean():.1%}" if m.any() else "-"
        print(f"   {t:.2f}   |     {m.mean():6.1%}      |      {acc}")


if __name__ == "__main__":
    main()