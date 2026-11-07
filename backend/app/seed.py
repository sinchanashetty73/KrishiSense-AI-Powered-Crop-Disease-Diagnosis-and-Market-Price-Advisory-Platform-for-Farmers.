"""Seeds reference data (crops, diseases) and, if SEED_DEMO_DATA=true, demo markets plus
SYNTHETIC price history so the app is usable before you load real mandi data.

TO CHANGE: add crops in CROPS, add/edit disease advice in DISEASES. Labels must match the
class names in ml_service/models/labels.json (created by training/train_disease.py).
"""
import math
import random
from datetime import timedelta

from sqlalchemy.orm import Session

from .models import Crop, Disease, MandiPrice, Market, utcnow
from .seed_advice import EXTRA_DISEASES

CROPS = {
    "Tomato": {"hi": "टमाटर", "kn": "ಟೊಮೇಟೊ"},
    "Potato": {"hi": "आलू", "kn": "ಆಲೂಗಡ್ಡೆ"},
    "Maize": {"hi": "मक्का", "kn": "ಮೆಕ್ಕೆಜೋಳ"},
    "Capsicum": {"hi": "शिमला मिर्च", "kn": "ದೊಣ್ಣೆ ಮೆಣಸಿನಕಾಯಿ"},
}

# Approximate storage life in days at normal village conditions. TO CHANGE: edit these numbers.
SHELF_LIFE_DAYS = {"Tomato": 10, "Potato": 90, "Maize": 180, "Capsicum": 10}

# Spray products per litre of water (INDICATIVE, typical extension-style doses; the product label always wins).
# TO CHANGE: have an agronomist review these before real use.
NEEM = {"name": "Neem oil (1500 ppm)", "kind": "organic", "dose": 5.0, "unit": "ml"}
MANCOZEB = {"name": "Mancozeb 75% WP", "kind": "chemical", "dose": 2.5, "unit": "g"}
COPPER = {"name": "Copper oxychloride 50% WP", "kind": "chemical", "dose": 3.0, "unit": "g"}
CHLORO = {"name": "Chlorothalonil 75% WP", "kind": "chemical", "dose": 2.0, "unit": "g"}
METAL = {"name": "Metalaxyl + Mancozeb", "kind": "chemical", "dose": 2.5, "unit": "g"}
ABAMECTIN = {"name": "Abamectin 1.9% EC", "kind": "chemical", "dose": 0.5, "unit": "ml"}
IMIDA = {"name": "Imidacloprid 17.8% SL (against whitefly vector)", "kind": "chemical", "dose": 0.3, "unit": "ml"}
PRODUCTS = {
    "Tomato___Early_blight": [NEEM, MANCOZEB, CHLORO],
    "Tomato___Late_blight": [COPPER, METAL, MANCOZEB],
    "Tomato___Bacterial_spot": [COPPER],
    "Tomato___Leaf_Mold": [CHLORO],
    "Tomato___Septoria_leaf_spot": [NEEM, MANCOZEB],
    "Tomato___Spider_mites Two-spotted_spider_mite": [NEEM, ABAMECTIN],
    "Tomato___Target_Spot": [MANCOZEB],
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus": [NEEM, IMIDA],
    "Potato___Early_blight": [NEEM, MANCOZEB],
    "Potato___Late_blight": [METAL, MANCOZEB],
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot": [MANCOZEB],
    "Corn_(maize)___Common_rust_": [MANCOZEB],
    "Corn_(maize)___Northern_Leaf_Blight": [MANCOZEB],
    "Pepper,_bell___Bacterial_spot": [COPPER],
}

# PlantVillage class names -> (crop, display name, symptoms, organic, chemical, prevention)
_GENERIC_CHEM = "Use only products registered for this crop; follow the label dose. Ask your agriculture officer."
DISEASES = {
    "Tomato___Early_blight": ("Tomato", "Early blight",
        "Brown spots with concentric rings on older leaves; leaves yellow and drop.",
        "Remove infected leaves; spray neem oil (3-5 ml/L); mulch to stop soil splash.",
        "Protectant fungicides such as mancozeb or chlorothalonil as per label.",
        "Rotate crops (2-3 years), stake plants, avoid overhead irrigation, use clean seed."),
    "Tomato___Late_blight": ("Tomato", "Late blight",
        "Large dark water-soaked patches on leaves and stems; white mould underneath in humid weather.",
        "Remove and destroy infected plants quickly; improve airflow; copper-based sprays.",
        "Systemic/protectant fungicides (e.g. metalaxyl + mancozeb) as per label; act early.",
        "Avoid planting in cool, wet spells; use resistant varieties; do not leave cull piles."),
    "Tomato___Bacterial_spot": ("Tomato", "Bacterial spot",
        "Small dark greasy spots on leaves and fruit; leaves may look ragged.",
        "Remove infected plants; avoid working in wet fields; copper sprays reduce spread.",
        "Copper-based bactericide as per label.",
        "Use disease-free seed/seedlings, drip irrigation, crop rotation."),
    "Tomato___Leaf_Mold": ("Tomato", "Leaf mould",
        "Pale yellow patches on top of leaves with olive-green mould underneath.",
        "Improve ventilation, reduce humidity, remove affected leaves.",
        _GENERIC_CHEM, "Space plants well; avoid wetting leaves; use resistant varieties."),
    "Tomato___Septoria_leaf_spot": ("Tomato", "Septoria leaf spot",
        "Many small round spots with grey centres and dark edges on lower leaves.",
        "Remove lower infected leaves; mulch; neem or copper sprays.",
        _GENERIC_CHEM, "Rotate crops, clear crop debris, avoid overhead watering."),
    "Tomato___Spider_mites Two-spotted_spider_mite": ("Tomato", "Spider mites",
        "Tiny yellow speckles, fine webbing under leaves, leaves turn bronze and dry.",
        "Spray water on leaf undersides; neem oil or soap spray; conserve natural predators.",
        "Miticide registered for tomato, as per label.",
        "Avoid dusty, water-stressed conditions; check leaf undersides weekly."),
    "Tomato___Target_Spot": ("Tomato", "Target spot",
        "Brown spots with rings like a target on leaves and fruit.",
        "Remove infected leaves; improve airflow; copper spray.",
        _GENERIC_CHEM, "Rotate crops; avoid dense planting and wet foliage."),
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus": ("Tomato", "Yellow leaf curl virus",
        "Leaves curl upward, turn yellow, plants stay stunted. Spread by whiteflies.",
        "Remove infected plants; yellow sticky traps; neem spray against whiteflies.",
        "No cure for the virus; control whiteflies with a registered insecticide.",
        "Use virus-tolerant varieties, insect nets in nursery, control weeds."),
    "Tomato___Tomato_mosaic_virus": ("Tomato", "Mosaic virus",
        "Mottled light/dark green leaves, distorted growth.",
        "Remove infected plants; wash hands and tools; do not smoke/handle tobacco before touching plants.",
        "No chemical cure.", "Use certified seed and resistant varieties; disinfect tools."),
    "Tomato___healthy": ("Tomato", "Healthy tomato leaf", "", "", "", "Keep monitoring weekly."),
    "Potato___Early_blight": ("Potato", "Early blight",
        "Dark brown spots with rings on older leaves.",
        "Remove infected leaves; neem oil; maintain good nutrition.",
        "Protectant fungicide (e.g. mancozeb) as per label.",
        "Rotate crops, use certified seed tubers, avoid water stress."),
    "Potato___Late_blight": ("Potato", "Late blight",
        "Dark, water-soaked patches that spread fast in cool wet weather; tubers can rot.",
        "Destroy infected plants; avoid overhead irrigation.",
        "Systemic + protectant fungicide as per label; start before symptoms in risky weather.",
        "Plant resistant varieties; hill up soil; destroy volunteer plants and cull piles."),
    "Potato___healthy": ("Potato", "Healthy potato leaf", "", "", "", "Keep monitoring weekly."),
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot": ("Maize", "Gray leaf spot",
        "Rectangular grey-tan lesions running along leaf veins.",
        "Rotate crops; bury residue; plant resistant hybrids.",
        _GENERIC_CHEM, "Avoid continuous maize; improve airflow; use resistant hybrids."),
    "Corn_(maize)___Common_rust_": ("Maize", "Common rust",
        "Small brick-red powdery pustules on both leaf surfaces.",
        "Usually mild; use resistant hybrids and early planting.",
        "Fungicide only if severe, as per label.", "Plant resistant hybrids."),
    "Corn_(maize)___Northern_Leaf_Blight": ("Maize", "Northern leaf blight",
        "Long grey-green cigar-shaped lesions on leaves.",
        "Rotate crops; bury residue; resistant hybrids.",
        _GENERIC_CHEM, "Use resistant hybrids; manage residue."),
    "Corn_(maize)___healthy": ("Maize", "Healthy maize leaf", "", "", "", "Keep monitoring weekly."),
    "Pepper,_bell___Bacterial_spot": ("Capsicum", "Bacterial spot",
        "Small water-soaked spots turning brown on leaves; raised scabby spots on fruit.",
        "Remove infected plants; copper sprays; avoid working when wet.",
        "Copper-based bactericide as per label.", "Use clean seed, drip irrigation, rotate crops."),
    "Pepper,_bell___healthy": ("Capsicum", "Healthy capsicum leaf", "", "", "", "Keep monitoring weekly."),
}

# name, district, state, lat, lon
DEMO_MARKETS = [
    ("Yeshwanthpur", "Bangalore", "Karnataka", 13.0280, 77.5400),
    ("Mysuru", "Mysore", "Karnataka", 12.2958, 76.6394),
    ("Hubballi", "Dharwad", "Karnataka", 15.3647, 75.1240),
    ("Mangaluru", "Dakshina Kannada", "Karnataka", 12.9141, 74.8560),
    ("Kolar", "Kolar", "Karnataka", 13.1360, 78.1290),
]
_BASE_PRICE = {"Tomato": 1800, "Potato": 1500, "Maize": 2100, "Capsicum": 3200}  # Rs/quintal


def seed_reference(db: Session) -> None:
    if db.query(Crop).count() == 0:
        for name, local in CROPS.items():
            db.add(Crop(name=name, local_names=local, shelf_life_days=SHELF_LIFE_DAYS.get(name)))
        db.commit()
    crops = {c.name: c for c in db.query(Crop).all()}
    for c in crops.values():
        if c.shelf_life_days is None and c.name in SHELF_LIFE_DAYS:
            c.shelf_life_days = SHELF_LIFE_DAYS[c.name]
    db.commit()
    existing = {d.label: d for d in db.query(Disease).all()}
    for label, (crop, name, sym, org, chem, prev) in DISEASES.items():
        if label in existing:
            if not existing[label].products and PRODUCTS.get(label):
                existing[label].products = PRODUCTS[label]
            continue
        db.add(Disease(label=label, crop_id=crops[crop].id, name=name,
                       is_healthy=label.endswith("healthy"), symptoms=sym,
                       organic_treatment=org, chemical_treatment=chem, prevention=prev,
                       products=PRODUCTS.get(label, [])))
    # Other PlantVillage crops (apple, grape, ...): no crop link, the crop is part of the display name.
    for label, (name, sym, org, chem, prev) in EXTRA_DISEASES.items():
        if label in existing:
            continue
        db.add(Disease(label=label, crop_id=None, name=name, is_healthy=label.endswith("healthy"),
                       symptoms=sym, organic_treatment=org, chemical_treatment=chem, prevention=prev,
                       products=[]))
    db.commit()


def seed_demo_prices(db: Session, days: int = 180) -> None:
    if db.query(Market).count() > 0:
        return
    rng = random.Random(42)
    markets = []
    for name, district, state, lat, lon in DEMO_MARKETS:
        m = Market(name=name, district=district, state=state, lat=lat, lon=lon)
        db.add(m)
        markets.append(m)
    db.commit()
    today = utcnow().date()
    for crop in db.query(Crop).all():
        base = _BASE_PRICE[crop.name]
        phase = rng.uniform(0, 6.28)
        for m in markets:
            factor = 1 + rng.uniform(-0.08, 0.08)
            walk = 0.0
            for i in range(days, -1, -1):
                d = today - timedelta(days=i)
                walk = 0.9 * walk + rng.gauss(0, 0.012)
                seasonal = 0.22 * math.sin(2 * math.pi * d.timetuple().tm_yday / 365 + phase)
                modal = round(base * factor * (1 + seasonal + walk), 0)
                db.add(MandiPrice(market_id=m.id, crop_id=crop.id, date=d,
                                  modal_price=modal, min_price=round(modal * 0.9),
                                  max_price=round(modal * 1.1),
                                  arrivals=round(rng.uniform(50, 400), 1)))
    db.commit()