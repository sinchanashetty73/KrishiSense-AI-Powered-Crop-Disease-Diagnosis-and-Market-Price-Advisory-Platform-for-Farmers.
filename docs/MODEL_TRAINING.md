# Model training guide

Two models: a **leaf disease classifier** (images) and a **price forecaster** (time series).

## 1. Disease classifier

### Data
| Dataset | Use | Notes |
|---|---|---|
| **PlantVillage** (Kaggle: "New Plant Diseases Dataset" or "PlantVillage") | training + validation | ~54k lab-style images, clean backgrounds. Models reach ~99%, which is **misleading** |
| **PlantDoc** (GitHub: pratikkayal/PlantDoc-Dataset) | real-field test set | ~2.5k photos from the web with messy backgrounds. Expect much lower accuracy. Report it |
| Your own photos | best test set | Even 100 to 200 photos from a nearby farm, labelled by an agriculture officer, are valuable |

Folder layout expected by the script (class folder names must start with the crop prefix):
```
data/plantvillage/Tomato___Late_blight/*.jpg
data/plantvillage/Potato___healthy/*.jpg
data/plantdoc_test/Tomato___Late_blight/*.jpg      # same class names as above (rename PlantDoc folders to match)
```
Default crops: `Tomato`, `Potato`, `Corn_(maize)`, `Pepper,_bell` (19 classes). Rice and onion are NOT in PlantVillage,
so use other datasets (e.g. Kaggle "Rice Leaf Diseases") if you want them, and add them to `seed.py`.

### Where to train
- **Colab (free GPU)**: upload `training/` and the dataset to Drive, `pip install -r requirements.txt`, run the command below. Easiest.
- **Your laptop**: works on CPU, about 20 to 40 min/epoch for the full set; try `--epochs 3` first.
- **AWS SageMaker / EC2 g4dn.xlarge**: only if you want AWS in the story; **stop the instance when done** (GPU cost).

### Run
```bash
cd training
pip install -r requirements.txt
python train_disease.py --data ./data/plantvillage --field-dir ./data/plantdoc_test --out ../models --epochs 8
```
Outputs in `models/`: `disease.onnx` (~6 MB), `labels.json`, `disease_metrics.json`
(`val_accuracy_plantvillage` and, if you gave `--field-dir`, `field_accuracy`).

Then restart the ML service: `docker compose restart ml_service`. `GET :8001/health` should show `"disease_model": true`.

### What the script does
1. MobileNetV3-Small pre-trained on ImageNet, new classification head.
2. Stage 1 trains only the head for 1/3 of the epochs, then stage 2 fine-tunes all layers at a 10x lower learning rate.
3. Heavy augmentation (random crop, flip, rotation, colour jitter) to help on field photos. Label smoothing to reduce overconfidence.
4. Keeps the best epoch by validation accuracy, exports ONNX (dynamic batch).

### Improving real-world accuracy (in order of impact)
1. Add field photos (PlantDoc + your own) to the **training** set, not just testing. Keep a separate untouched field test set.
2. Add a "not a leaf / other" class using random photos (hands, soil, sky, other plants).
3. Try `efficientnet_b0` (edit `models.mobilenet_v3_small` in the script), bigger images (256), more epochs.
4. Use the in-app "Was this correct?" feedback (`scans.feedback`, `true_label`) to collect hard examples and retrain.
5. Report per-class precision/recall and a confusion matrix, not just accuracy.
6. The app rejects predictions below `CONFIDENCE_THRESHOLD` (0.6) as "not sure". Tune it on field data: higher = fewer wrong answers but more "not sure".

### Honest-reporting template for your report/resume
> PlantVillage validation accuracy: __%. Real-field accuracy (PlantDoc / own photos, N=__): __%.
> Confidence threshold 0.6 abstains on __% of field images; accuracy on the remaining images: __%.

## 2. Price forecaster

Handled by `ml_service/train_price.py` and runs from the database:
```bash
docker compose --profile jobs run --rm retrain
curl -X POST http://localhost:8001/admin/reload
```
- Features: last 14 prices normalised by their mean, plus two slope features. One model for all crops and markets.
- Model: scikit-learn `HistGradientBoostingRegressor` (one step ahead, recursive for multi-day).
- Validation: walk-forward. Trains on the first 80% of dates, tests on the last 20%, and compares the **7-day-ahead MAPE with a
  naive baseline** ("price stays the same"). A new model is promoted only if it beats the naive baseline **and** the currently deployed model.
- Output: `models/price_model.joblib` and `models/price_metrics.json`.
- Needs at least 54 days of history per crop/market. With the **synthetic demo data** the metrics mean nothing (it is made up);
  retrain on real data.

Ideas: add arrivals, rainfall, day-of-week and festival flags as features; try per-crop models; add quantile regression for better ranges;
compare against Prophet/SARIMA in a notebook and show the table in your report.

## 3. Scheduling retraining
Weekly: EventBridge Scheduler → ECS RunTask with the `ml_service` image and command `python train_price.py --out /models`
(mount EFS, or change the script to read/write the model from S3, then call `/admin/reload`). See `AWS_DEPLOYMENT.md`.
