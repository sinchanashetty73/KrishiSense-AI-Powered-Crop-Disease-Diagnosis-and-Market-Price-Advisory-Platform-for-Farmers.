# KrishiSense: Crop Disease and Price Advisory Platform

KrishiSense helps farmers in two ways. They photograph a leaf and get a **disease diagnosis with treatment advice**.
They also see **market prices, a 7-day price forecast, the best market after transport cost, price alerts and a
weather-based spray advisory**, in English, Hindi or Kannada.

It is a full-stack data and ML project: a React web app (PWA), a FastAPI backend, a separate ML inference service
(ONNX), a price-ingestion pipeline with a data-quality gate, and Docker packaging. AWS deployment is **designed but
not yet done** (see [AWS deployment](#aws-deployment-planned)).

> **Status:** this is a work in progress. The "Project status" section says exactly what has been built, what has
> been tested and what has not.

---

## Table of contents
1. [Project status](#project-status)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Tech stack](#tech-stack)
5. [Project structure](#project-structure)
6. [How to run](#how-to-run)
7. [Machine-learning models](#machine-learning-models)
8. [Data pipeline](#data-pipeline)
9. [Configuration](#configuration-environment-variables)
10. [Testing](#testing)
11. [AWS deployment (planned)](#aws-deployment-planned)
12. [Where to make changes](#where-to-make-changes)
13. [Roadmap](#roadmap)
14. [Limitations](#limitations)
15. [Data licences](#data-licences-and-credits)

---

## Project status

| Area | Status |
|---|---|
| Backend API (auth, scans, prices, forecast, alerts, marketplace, stock, chat) | Built. 48 automated tests pass |
| Frontend (React PWA, 3 languages, 11 pages) | Built. Production build succeeds |
| Leaf disease model | **Trained** (119 classes, MobileNetV3-Small, exported to ONNX) and running in the app |
| Price forecast model | Code written and unit-tested. **Not trained on real data yet** (the app uses a baseline forecast) |
| Market prices | The app seeds **synthetic demo prices**. The real-price ingestion job is written but **not yet validated against the live API** |
| Docker / Docker Compose | Files written. **Not yet built end to end** |
| MySQL | Used in Docker Compose. Local development uses SQLite. MySQL runtime is **not yet tested** |
| SMS (Amazon SNS) and web push | Code written. Real sending is **not tested** (development mode only logs messages) |
| **AWS deployment** | **Not deployed.** Design and CI/CD workflow are written (see below) |
| Advice text for diseases | General guidance. **Not reviewed by an agronomist** |

---

## Features

| Feature | Page | Notes |
|---|---|---|
| Leaf disease scan with symptoms, organic and chemical treatment and prevention | Scan | Says "Not sure" with retake tips when the model's confidence is below a threshold, instead of guessing |
| Dosage calculator: water, tanks and product amount for a given land area | Spray | Doses are indicative only |
| Weather-based spray advisory: best spray windows in the next 48 hours | Spray, Home | Free Open-Meteo API (no key). Rules: wind, rain, heat, daylight, plus a fungal-risk warning |
| Multilingual assistant (English, Hindi, Kannada) with voice input and output | Assistant | Rule-based. Answers from the app's own data. Uses the browser Web Speech API |
| Farmer marketplace: list produce with photo and price, buyers send inquiries | Market | The seller's phone number is never shown publicly |
| Inventory: harvest quantity, storage, estimated value at today's price, "sell soon" alerts | Stock | Shelf life per crop is approximate |
| Disease map (Leaflet + OpenStreetMap) and district counts | Nearby diseases | Anonymised, coarse location only |
| Prices, 7-day forecast, best market after transport cost, profit calculator | Prices | Forecast advice: wait / sell / stable (threshold plus or minus 5%) |
| Price alerts by SMS and web push | Alerts | Above or below a price, or a rise or fall of X% over 3 days. One message per crossing |
| Home dashboard | Home | Spray status, triggered alerts, stock to sell soon, last scan |

Login uses a phone number with an OTP and JWT tokens. In development mode the OTP is shown on screen.

---

## Architecture

```
React PWA (nginx) ──/api──► FastAPI backend ──► ML service (ONNX disease model + price forecaster)
                               │   │
                               │   └──► S3 (scan images; local folder in development)
                               ▼
                         MySQL / SQLite ◄── ingest job (market prices) / retrain job
                               ▲
                  Open-Meteo weather API ──┘ (spray advisory, called by the backend)
```

- The **backend** owns users, scans, prices, alerts and the database. It calls the **ML service** over HTTP for
  predictions, and falls back to a simple baseline forecast if the ML service is unavailable.
- The **ML service** is separate so the models can be updated and scaled independently of the API.
- The **ingest job** and the **retrain job** run on demand or on a schedule (not as part of the API process).

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React, Vite, Leaflet, service worker (installable PWA), Web Speech API |
| Backend | Python, FastAPI, SQLAlchemy, Pydantic, JWT auth, pytest |
| ML service | FastAPI, ONNX Runtime (disease model), scikit-learn gradient boosting (price forecast) |
| Model training | PyTorch, torchvision (MobileNetV3-Small, transfer learning), trained on Google Colab (T4 GPU) |
| Data pipeline | Python, httpx, SQLAlchemy, data-quality checks, raw data saved to S3 or a local folder |
| Database | MySQL 8 (Docker) or SQLite (local development) |
| Packaging and CI/CD | Docker, Docker Compose, GitHub Actions (ECR and ECS workflow written) |
| Planned cloud | AWS: ECR, ECS Fargate, RDS MySQL, ALB, S3, SNS, EventBridge |

---

## Project structure

```
krishisense/
├── README.md
├── docker-compose.yml          # db, backend, ml_service, frontend + optional jobs (ingest, retrain, alerts)
├── .env.example                # copy to .env and edit (never commit .env)
├── .gitignore
├── .github/
│   └── workflows/
│       └── deploy.yml          # CI/CD to AWS (ECR + ECS). Written, not yet used
├── docs/
│   ├── MODEL_TRAINING.md       # how to train the disease model
│   └── AWS_DEPLOYMENT.md       # AWS deployment guide (EC2 path and ECS path)
├── models/                     # trained model files go here (git-ignored, see "Machine-learning models")
│   └── .gitkeep                # expects disease.onnx, labels.json, (optional) price_model files
│
├── backend/                    # FastAPI API
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pytest.ini
│   ├── scripts/
│   │   └── generate_vapid.py   # creates keys for web push notifications
│   ├── app/
│   │   ├── main.py             # app startup, routers, database creation and seeding
│   │   ├── config.py           # settings from environment variables
│   │   ├── database.py         # SQLAlchemy engine and session
│   │   ├── models.py           # database tables
│   │   ├── schemas.py          # request/response models
│   │   ├── security.py         # JWT and OTP helpers
│   │   ├── deps.py             # shared dependencies (current user, database session)
│   │   ├── storage.py          # saves scan images (local or S3)
│   │   ├── ml_client.py        # calls the ML service
│   │   ├── seed.py             # reference data: crops, diseases, advice, products
│   │   ├── seed_advice.py      # extra advice for apple, grape, cherry, peach, citrus, etc.
│   │   ├── seed_data.py        # demo markets and synthetic demo prices
│   │   ├── core/               # shared config, db and security helpers
│   │   ├── routers/            # API endpoints
│   │   │   ├── auth.py         # OTP login
│   │   │   ├── users.py        # profile and location
│   │   │   ├── scans.py        # leaf scan -> ML service -> advice
│   │   │   ├── prices.py       # price history, 7-day forecast, best market, profit
│   │   │   ├── advisory.py     # weather-based spray advisory and dosage
│   │   │   ├── alerts.py       # price alerts
│   │   │   ├── market.py       # farmer marketplace
│   │   │   ├── inventory.py    # stock / harvest tracking
│   │   │   ├── outbreaks.py    # disease map data
│   │   │   ├── chat.py         # multilingual assistant
│   │   │   ├── meta.py         # crops, markets, languages
│   │   │   ├── admin.py        # admin endpoints
│   │   │   └── internal.py     # endpoints used by scheduled jobs
│   │   ├── services/
│   │   │   ├── weather.py      # Open-Meteo client + spray rules
│   │   │   ├── dosage.py       # dose calculation
│   │   │   ├── pricing.py      # price helpers
│   │   │   ├── alerting.py     # alert rule evaluation
│   │   │   ├── alert_dispatch.py  # builds and sends alert messages
│   │   │   ├── sms.py          # SMS sending (log mode or Amazon SNS)
│   │   │   ├── push.py         # web push sending
│   │   │   ├── geo.py          # distance helpers
│   │   │   ├── storage.py      # image storage
│   │   │   └── ml_client.py    # ML service client
│   │   └── jobs/
│   │       └── run_alerts.py   # daily alert job
│   └── tests/                  # 48 tests: API, features, alerts
│
├── ml_service/                 # model inference and price-model training
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py                  # /health, /predict/disease, /forecast, /admin/reload
│   ├── forecasting.py          # price features, model forecast, baseline forecast
│   ├── train_price.py          # trains the price forecaster, compares it with a naive baseline
│   └── test_ml_service.py
│
├── training/                   # disease model training (run on Google Colab)
│   ├── requirements.txt
│   ├── train_disease.py        # trains MobileNetV3-Small, exports disease.onnx + labels.json
│   ├── prepare_plantwild.py    # merges PlantWild folders into the PlantVillage layout, holds out test photos
│   └── threshold_report.py     # accuracy vs confidence threshold on held-out photos
│
├── pipelines/                  # data ingestion
│   ├── Dockerfile
│   ├── requirements.txt
│   └── ingest_prices.py        # API -> raw JSON -> validate -> upsert into the database
│
└── frontend/                   # React PWA
    ├── Dockerfile
    ├── nginx.conf
    ├── package.json
    ├── vite.config.js          # dev proxy: /api -> backend
    ├── index.html
    ├── public/
    │   ├── manifest.webmanifest  # PWA manifest
    │   └── sw.js                 # service worker (push + caching)
    └── src/
        ├── main.jsx
        ├── App.jsx             # routing and bottom navigation
        ├── api.js              # API client
        ├── push.js             # web push subscription
        ├── i18n.js, i18nExtra.js   # English / Hindi / Kannada text
        ├── styles.css
        └── pages/
            ├── Login.jsx   Home.jsx      Scan.jsx     Spray.jsx
            ├── Prices.jsx  Market.jsx    Stock.jsx    Chat.jsx (assistant)
            ├── Alerts.jsx  Outbreaks.jsx Profile.jsx
```

---

## How to run

### Prerequisites
- Python 3.11 or newer
- Node.js 18 or newer
- (Optional) Docker Desktop, for the Docker route
- Git

### Option A: Run with Docker Compose (all services)
```bash
git clone https://github.com/<your-username>/krishisense.git
cd krishisense
cp .env.example .env        # Windows PowerShell: Copy-Item .env.example .env
# edit .env: set DB_PASSWORD (letters and digits only) and JWT_SECRET
docker compose up --build
```
- App: http://localhost:3000
- API documentation: http://localhost:8000/api/docs
- ML service health: http://localhost:8001/health

Log in with any 10-digit number. In development mode the OTP is displayed on screen.

> The Docker images have not been built end to end yet. If a build fails, the error message points to the cause. Option B
> is the route that has been tested.

### Option B: Run without Docker (development, tested)
Use three terminals.

**Terminal 1: ML service**
```bash
cd ml_service
python -m venv .venv
.venv\Scripts\activate            # Windows. Linux/macOS: . .venv/bin/activate
pip install -r requirements.txt
# Windows PowerShell:
$env:MODELS_DIR="..\models"
python -m uvicorn app:app --port 8001
```
Check http://127.0.0.1:8001/health. It should show `"disease_model": true` once the model files are in `models/`.

**Terminal 2: Backend** (uses a local SQLite file, no MySQL needed)
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
# Windows PowerShell:
$env:ML_SERVICE_URL="http://127.0.0.1:8001"
$env:CONFIDENCE_THRESHOLD="0.5"
python -m uvicorn app.main:app --reload --port 8000
```

**Terminal 3: Frontend**
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173. Vite proxies `/api` to port 8000.

### Common problems
| Problem | Fix |
|---|---|
| "Disease detection is temporarily unavailable" | The ML service is not running, or the backend does not have `ML_SERVICE_URL` set |
| `/health` shows `disease_model: false` | `disease.onnx` and `labels.json` are not in the folder `MODELS_DIR` points to |
| `ModuleNotFoundError` in the backend | Run `pip install -r requirements.txt` inside `backend/` |
| Port already in use | Another copy is running. Find it with `netstat -ano \| findstr :8000` and stop it with `taskkill /PID <pid> /F` |
| Old database errors after pulling new code | Delete `backend/dev.db` and restart (it is recreated and reseeded) |

---

## Machine-learning models

### 1. Leaf disease classifier
- **Model:** MobileNetV3-Small, pretrained on ImageNet, fine-tuned in two stages (new head first, then the full network at a lower learning rate). Label smoothing, AdamW and image augmentation are used. Input size 224 pixels. Exported to **ONNX** and served with ONNX Runtime.
- **Data:** PlantVillage (38 classes, 54,305 images) merged with PlantWild v2 (real-world photos, about 11,000 images in the kept classes). PlantWild classes with the same disease as PlantVillage are merged into one class. Classes with too few images were dropped. Final model: **119 classes** across many fruits and vegetables.
- **Training:** Google Colab (T4 GPU), 12 epochs. Data is downloaded inside Colab to avoid large uploads. Scripts: `training/prepare_plantwild.py`, `training/train_disease.py`. See `docs/MODEL_TRAINING.md`.

**Results (measured, not estimated):**

| Test | Result |
|---|---|
| Validation accuracy (random split of the training data) | 93.7% |
| Held-out real-world photos (PlantWild, 1,620 images never used in training), top-1 | **58.7%** |
| Same held-out photos, correct answer within top 5 | **85.6%** |

The validation number is optimistic, because PlantVillage photos of the same leaf can appear on both sides of a random
split. The held-out real-photo number is the honest one.

**Confidence threshold.** The app answers only when the model's confidence is above a threshold, otherwise it says
"Not sure" and gives retake tips. The threshold was chosen from a table measured on the held-out photos
(`training/threshold_report.py`):

| Threshold | Photos answered | Answers that are correct |
|---|---|---|
| 0.30 | 75% | 70% |
| 0.40 | 64% | 76% |
| **0.50** | **52%** | **82%** |
| 0.60 | 42% | 87% |
| 0.80 | 26% | 94% |

A higher threshold gives fewer but more reliable answers. Set it with `CONFIDENCE_THRESHOLD` (0.5 is a good demo value).

**Model files.** The trained files are not stored in Git (`models/*` is git-ignored). Put these three files in `models/`:
`disease.onnx`, `labels.json`, `disease_metrics.json`. To rebuild them, follow `docs/MODEL_TRAINING.md`. Without the
files, the ML service runs in **demo mode** (fake but deterministic answers, flagged in the UI).

### 2. Price forecaster
- Gradient-boosting regressor (scikit-learn) that predicts the next day's price from the last 14 days, scaled by their mean so one model works for every crop and market. Multi-day forecasts are made recursively.
- If no trained model exists, a **damped-trend baseline** is used.
- `ml_service/train_price.py` evaluates with a walk-forward split and **saves the new model only if it beats the naive "tomorrow equals today" baseline** and any model already deployed.
- **Status:** not yet trained on real data, because only synthetic demo prices exist so far (see next section).

---

## Data pipeline

`pipelines/ingest_prices.py`:
1. Fetches daily market prices from the Indian government open-data API (Agmarknet on data.gov.in, free API key needed).
2. Saves the raw response (to S3 if `S3_BUCKET` is set, otherwise to `./data/raw/`).
3. **Cleans and validates** the records: parses dates and numbers, drops rows with missing or impossible values (price out of range, min greater than max, future dates, unknown crops) and aborts if too few valid rows remain.
4. Upserts into the database (works on MySQL and SQLite, so repeated runs do not create duplicates).

The API returns only recent days, so history must be collected daily (or backfilled) before the price model can be
trained (about 55 days per crop and market are needed).

```bash
# local example (PowerShell)
cd pipelines
pip install -r requirements.txt
$env:DATA_GOV_API_KEY="your-key"
$env:DATABASE_URL="sqlite:///../backend/dev.db"
python ingest_prices.py --state Karnataka
```
Then, once enough history exists:
```bash
cd ml_service
python train_price.py --db-url sqlite:///../backend/dev.db --out ../models
```
To remove the synthetic demo prices, delete `backend/dev.db` and start the backend with `SEED_DEMO_DATA=false`.

---

## Configuration (environment variables)

Copy `.env.example` to `.env`. Never commit `.env`.

| Variable | Meaning |
|---|---|
| `DB_PASSWORD` | MySQL password for Docker Compose (letters and digits only) |
| `JWT_SECRET` | Secret for signing login tokens. Use a long random value |
| `DEV_OTP_ECHO` | `true` shows the OTP on screen (development). **Must be `false` in production** |
| `SEED_DEMO_DATA` | `true` creates synthetic demo prices. Set `false` once real data is loaded |
| `CORS_ORIGINS` | Allowed website origins. Use your real domain in production |
| `CONFIDENCE_THRESHOLD` | Below this, a scan says "Not sure" (0.5 recommended, 0.6 is the default) |
| `ML_SERVICE_URL` | Address of the ML service (default `http://ml_service:8001`) |
| `MODELS_DIR` | Folder with the model files (ML service) |
| `S3_BUCKET`, `AWS_REGION` | Store scan images in S3. Leave empty to store locally |
| `DATA_GOV_API_KEY`, `INGEST_STATE` | Price ingestion job |
| `SMS_PROVIDER` | `log` (print only) or `sns` (real SMS through Amazon SNS) |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` | Web push keys. Create with `python backend/scripts/generate_vapid.py` |

---

## Testing

```bash
cd backend && pytest          # 48 tests: auth, scans, prices, alerts, marketplace, stock, chat
cd ml_service && pytest       # ML service and price-training tests
cd frontend && npm run build  # production build check
```

---

## AWS deployment (planned)

> **Not deployed yet.** This section describes the intended design. The Dockerfiles, the GitHub Actions workflow
> (`.github/workflows/deploy.yml`) and the guide (`docs/AWS_DEPLOYMENT.md`) are written, but nothing has been run on AWS.
> This section will be updated after the first real deployment.

**Path A: quick and cheap (about one hour)**
One EC2 instance runs the same `docker compose up`, with a domain and HTTPS in front.

**Path B: production style**

| Component | AWS service |
|---|---|
| Container images (backend, ML service, frontend) | Amazon ECR |
| Running the containers | ECS Fargate |
| Database | Amazon RDS for MySQL |
| HTTPS entry point | Application Load Balancer + ACM certificate |
| Scan image storage | Amazon S3 (private bucket, IAM task role, no access keys) |
| SMS price alerts | Amazon SNS |
| Scheduled jobs (price ingestion, alerts, retraining) | Amazon EventBridge Scheduler running ECS tasks |
| Logs | Amazon CloudWatch |
| Build and deploy | GitHub Actions: build images, push to ECR, update the ECS services |

**Production checklist**
- [ ] `DEV_OTP_ECHO=false` and real SMS through SNS
- [ ] Strong random `JWT_SECRET`, and `CORS_ORIGINS` set to the real domain
- [ ] HTTPS everywhere
- [ ] Private S3 bucket and an IAM role instead of keys
- [ ] Database migrations with Alembic (today the app only creates missing tables)
- [ ] Privacy notice (the app stores phone numbers, locations and photos)

---

## Where to make changes

| I want to... | Change this |
|---|---|
| Add a crop | `backend/app/seed.py` (`CROPS`, `DISEASES`), `pipelines/ingest_prices.py` (`COMMODITIES`) |
| Edit treatment advice | `backend/app/seed.py`, `backend/app/seed_advice.py` (labels must match `models/labels.json`) |
| Change the "not sure" threshold | `CONFIDENCE_THRESHOLD` in `.env` |
| Change spray rules (wind, rain, heat) | `backend/app/services/weather.py` (constants at the top) |
| Change the forecast advice rule (plus or minus 5%) | `backend/app/routers/prices.py` |
| Change the forecast model | `ml_service/train_price.py` and `ml_service/forecasting.py` |
| Change the disease model | `training/train_disease.py` (input size must match `IMG_SIZE` in `ml_service/app.py`) |
| Real SMS | `backend/app/services/sms.py` |
| Add a language | `frontend/src/i18n.js` |
| Add a database table | `backend/app/models.py` (and a migration in production) |

---

## Roadmap
1. Load real market prices, collect history, train and evaluate the price model against the naive baseline.
2. Show the top 3 possible diseases when a scan is uncertain.
3. Advice text for all remaining disease classes, reviewed by an agriculture expert.
4. Improve real-photo accuracy (class balancing, a larger model, more field photos).
5. Build and test the Docker images, then deploy to AWS and update this README.
6. Weather-based disease risk alerts, offline photo queue, Grad-CAM explanations.

---

## Limitations
- The disease model is much less accurate on real field photos than on clean dataset photos (58.7% top-1 on held-out real photos). Treat results as a suggestion, not a diagnosis.
- Price forecasts use past prices only. They cannot see weather, policy or supply shocks.
- Treatment text is general guidance, not a prescription. Always follow the product label and ask a local agriculture officer.
- Current prices in the app are synthetic until real data is ingested.

---

## Data licences and credits
- **PlantVillage** dataset (leaf images).
- **PlantWild** dataset, licence **CC BY-NC-ND 4.0** (non-commercial use only). Do not use models trained on it commercially without checking the terms.
- Weather data: **Open-Meteo** (free, non-commercial use). Maps: **OpenStreetMap** and **Leaflet**.
- Price data: Agmarknet via data.gov.in (Government of India Open Data licence).