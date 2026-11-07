"""Multilingual (English / Hindi / Kannada) assistant for farmers.

This is a RULE-BASED assistant: it detects the intent from keywords and answers with real data from
the database and the weather service. It does not generate free text, so it cannot invent advice.
UPGRADE PATH: replace `detect_intent` + `answer` with an LLM that calls these same functions as tools.
Voice input/output happens in the browser (Web Speech API), see frontend/src/pages/Chat.jsx.

TO CHANGE: add keywords in KEYWORDS, add words in the REPLIES dict (one block per language).
Have native speakers review the Hindi and Kannada text before real use.
"""
import re
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user
from ..models import Crop, Disease, InventoryItem, Listing, MandiPrice, Scan, User
from ..schemas import ChatIn, ChatOut
from ..services import dosage, weather
from ..services.pricing import latest_avg_price, latest_by_market
from .inventory import _out as inventory_out

router = APIRouter(tags=["assistant"])

KEYWORDS = {
    "dosage": ["dose", "dosage", "how much to spray", "acre", "मात्रा", "खुराक", "एकड़", "एकड", "ಪ್ರಮಾಣ", "ಡೋಸ್", "ಎಕರೆ"],
    "spray": ["spray", "weather", "rain", "wind", "छिड़काव", "स्प्रे", "मौसम", "बारिश", "हवा",
              "ಸಿಂಪಡಣೆ", "ಸ್ಪ್ರೇ", "ಹವಾಮಾನ", "ಮಳೆ", "ಗಾಳಿ"],
    "inventory": ["stock", "inventory", "stored", "storage", "भंडार", "स्टॉक", "ದಾಸ್ತಾನು", "ಸ್ಟಾಕ್"],
    "market": ["marketplace", "buyer", "sell my", "list my", "खरीदार", "बेचना", "बेचें", "ಖರೀದಿದಾರ", "ಮಾರಾಟ ಮಾಡ"],
    "disease": ["disease", "treatment", "cure", "medicine", "blight", "mold", "mould", "rust", "virus", "mite",
                "रोग", "बीमारी", "इलाज", "उपचार", "दवा", "ರೋಗ", "ಚಿಕಿತ್ಸೆ", "ಔಷಧ"],
    "price": ["price", "rate", "cost", "mandi", "sell", "worth", "भाव", "दाम", "कीमत", "रेट", "मंडी",
              "ಬೆಲೆ", "ದರ", "ಮಾರುಕಟ್ಟೆ"],
}
ORDER = ["dosage", "spray", "inventory", "market", "disease", "price"]

REPLIES = {
    "en": {
        "need_crop": "Which crop? For example: tomato, potato, maize or capsicum.",
        "price": "{crop}: average latest mandi price is Rs {avg} per quintal. Best market: {market} at Rs {best}.{trend}",
        "trend": " Last 7 days: {chg:+.1f}%.",
        "no_price": "I have no price data for {crop} yet.",
        "need_location": "Please save your location in Profile so I can check the weather for your farm.",
        "spray_good": "Good time to spray now. Wind {wind} km/h, rain chance {rain}%.",
        "spray_bad": "Not a good time to spray now ({reasons}).",
        "next_window": " Next good window: {start} to {end}.",
        "no_window": " No good spraying window in the next 48 hours.",
        "fungal": " Warning: warm, humid weather is expected, so fungal disease risk is high. Check your plants.",
        "weather_down": "I cannot reach the weather service right now. Please try again later.",
        "r_wind": "strong wind", "r_rain": "rain likely", "r_heat": "too hot", "r_night": "night time",
        "disease_info": "{name} ({crop}). Symptoms: {sym} Organic: {org} Chemical: {chem} Prevention: {prev} Always confirm chemical use with your agriculture officer.",
        "healthy": "Your last scan looked healthy. Keep checking weekly.",
        "no_last_scan": "Tell me the disease name, or scan a leaf first in the Scan tab.",
        "need_area": "How many acres do you want to spray? For example: 'dose for 2 acres'.",
        "no_products": "I have no spray product list for this problem. See the treatment advice instead.",
        "dosage_result": "{name}, {area} acre(s): about {water} L of water ({tanks} tanks of {tank_l} L). {items}. Follow the product label.",
        "inventory": "You have {qty} quintals in stock worth about Rs {value}. {soon} item(s) should be sold soon.",
        "inventory_empty": "Your stock list is empty. Add your harvest in the Stock tab.",
        "market_info": "Open the Market tab to list your produce with a photo and a price. Buyers contact you through inquiries.{count}",
        "market_count": " There are {n} active listing(s) right now.",
        "help": "I can help with crop prices, spray timing (weather), disease treatment, dosage per acre, your stock and the marketplace. Try one of the suggestions below.",
        "suggestions": ["Tomato price", "When should I spray?", "Dose for 2 acres", "My stock"],
    },
    "hi": {
        "need_crop": "कौन सी फसल? जैसे: टमाटर, आलू, मक्का या शिमला मिर्च।",
        "price": "{crop}: ताज़ा औसत मंडी भाव ₹{avg} प्रति क्विंटल है। सबसे अच्छी मंडी: {market}, ₹{best}।{trend}",
        "trend": " पिछले 7 दिन: {chg:+.1f}%।",
        "no_price": "{crop} का अभी कोई भाव डेटा नहीं है।",
        "need_location": "कृपया प्रोफ़ाइल में अपना स्थान सहेजें ताकि मैं आपके खेत का मौसम देख सकूँ।",
        "spray_good": "अभी छिड़काव का अच्छा समय है। हवा {wind} किमी/घंटा, बारिश की संभावना {rain}%।",
        "spray_bad": "अभी छिड़काव का सही समय नहीं है ({reasons})।",
        "next_window": " अगला अच्छा समय: {start} से {end}।",
        "no_window": " अगले 48 घंटों में छिड़काव का अच्छा समय नहीं है।",
        "fungal": " चेतावनी: गर्म और नमी वाला मौसम रहेगा, इसलिए फफूंद रोग का खतरा ज़्यादा है। पौधों की जाँच करें।",
        "weather_down": "अभी मौसम सेवा से जुड़ नहीं पा रहा। कृपया बाद में कोशिश करें।",
        "r_wind": "तेज़ हवा", "r_rain": "बारिश की संभावना", "r_heat": "बहुत गर्मी", "r_night": "रात का समय",
        "disease_info": "{name} ({crop})। लक्षण: {sym} जैविक: {org} रासायनिक: {chem} बचाव: {prev} रसायन इस्तेमाल करने से पहले कृषि अधिकारी से पुष्टि ज़रूर करें।",
        "healthy": "आपकी पिछली जाँच में पौधा स्वस्थ दिखा। हर हफ्ते जाँचते रहें।",
        "no_last_scan": "रोग का नाम बताइए, या पहले स्कैन टैब में पत्ती की जाँच करें।",
        "need_area": "कितने एकड़ में छिड़काव करना है? जैसे: '2 एकड़ की मात्रा'।",
        "no_products": "इस समस्या के लिए दवा की सूची नहीं है। कृपया उपचार की सलाह देखें।",
        "dosage_result": "{name}, {area} एकड़: लगभग {water} लीटर पानी ({tank_l} लीटर के {tanks} टैंक)। {items}। दवा के लेबल का पालन करें।",
        "inventory": "आपके पास {qty} क्विंटल स्टॉक है, कीमत लगभग ₹{value}। {soon} स्टॉक जल्दी बेचना चाहिए।",
        "inventory_empty": "आपकी स्टॉक सूची खाली है। स्टॉक टैब में अपनी फसल जोड़ें।",
        "market_info": "फोटो और भाव के साथ अपनी उपज डालने के लिए मार्केट टैब खोलें। खरीदार पूछताछ से आपसे संपर्क करेंगे।{count}",
        "market_count": " अभी {n} सक्रिय लिस्टिंग हैं।",
        "help": "मैं फसल के भाव, छिड़काव का समय (मौसम), रोग का उपचार, प्रति एकड़ मात्रा, आपका स्टॉक और मार्केटप्लेस में मदद कर सकता हूँ। नीचे दिए सुझाव आज़माएँ।",
        "suggestions": ["टमाटर का भाव", "छिड़काव कब करूँ?", "2 एकड़ की मात्रा", "मेरा स्टॉक"],
    },
    "kn": {
        "need_crop": "ಯಾವ ಬೆಳೆ? ಉದಾಹರಣೆಗೆ: ಟೊಮೇಟೊ, ಆಲೂಗಡ್ಡೆ, ಮೆಕ್ಕೆಜೋಳ ಅಥವಾ ದೊಣ್ಣೆ ಮೆಣಸಿನಕಾಯಿ.",
        "price": "{crop}: ಇತ್ತೀಚಿನ ಸರಾಸರಿ ಮಾರುಕಟ್ಟೆ ಬೆಲೆ ಕ್ವಿಂಟಾಲ್‌ಗೆ ₹{avg}. ಉತ್ತಮ ಮಾರುಕಟ್ಟೆ: {market}, ₹{best}.{trend}",
        "trend": " ಕಳೆದ 7 ದಿನ: {chg:+.1f}%.",
        "no_price": "{crop} ಬೆಲೆ ಮಾಹಿತಿ ಇನ್ನೂ ಇಲ್ಲ.",
        "need_location": "ನಿಮ್ಮ ಜಮೀನಿನ ಹವಾಮಾನ ನೋಡಲು ಪ್ರೊಫೈಲ್‌ನಲ್ಲಿ ನಿಮ್ಮ ಸ್ಥಳವನ್ನು ಉಳಿಸಿ.",
        "spray_good": "ಈಗ ಸಿಂಪಡಣೆಗೆ ಉತ್ತಮ ಸಮಯ. ಗಾಳಿ {wind} ಕಿಮೀ/ಗಂ, ಮಳೆ ಸಾಧ್ಯತೆ {rain}%.",
        "spray_bad": "ಈಗ ಸಿಂಪಡಣೆಗೆ ಸೂಕ್ತ ಸಮಯವಲ್ಲ ({reasons}).",
        "next_window": " ಮುಂದಿನ ಉತ್ತಮ ಸಮಯ: {start} ರಿಂದ {end}.",
        "no_window": " ಮುಂದಿನ 48 ಗಂಟೆಗಳಲ್ಲಿ ಸಿಂಪಡಣೆಗೆ ಉತ್ತಮ ಸಮಯ ಇಲ್ಲ.",
        "fungal": " ಎಚ್ಚರಿಕೆ: ಬೆಚ್ಚಗಿನ, ತೇವಾಂಶದ ಹವಾಮಾನ ಇರುವುದರಿಂದ ಶಿಲೀಂಧ್ರ ರೋಗದ ಅಪಾಯ ಹೆಚ್ಚು. ಗಿಡಗಳನ್ನು ಪರೀಕ್ಷಿಸಿ.",
        "weather_down": "ಈಗ ಹವಾಮಾನ ಸೇವೆ ಲಭ್ಯವಿಲ್ಲ. ದಯವಿಟ್ಟು ನಂತರ ಪ್ರಯತ್ನಿಸಿ.",
        "r_wind": "ಬಲವಾದ ಗಾಳಿ", "r_rain": "ಮಳೆ ಸಾಧ್ಯತೆ", "r_heat": "ತುಂಬಾ ಬಿಸಿ", "r_night": "ರಾತ್ರಿ ಸಮಯ",
        "disease_info": "{name} ({crop}). ಲಕ್ಷಣಗಳು: {sym} ಸಾವಯವ: {org} ರಾಸಾಯನಿಕ: {chem} ತಡೆಗಟ್ಟುವಿಕೆ: {prev} ರಾಸಾಯನಿಕ ಬಳಸುವ ಮೊದಲು ಕೃಷಿ ಅಧಿಕಾರಿಯನ್ನು ಸಂಪರ್ಕಿಸಿ.",
        "healthy": "ನಿಮ್ಮ ಕೊನೆಯ ಪರೀಕ್ಷೆಯಲ್ಲಿ ಸಸ್ಯ ಆರೋಗ್ಯವಾಗಿತ್ತು. ವಾರಕ್ಕೊಮ್ಮೆ ಪರೀಕ್ಷಿಸಿ.",
        "no_last_scan": "ರೋಗದ ಹೆಸರು ಹೇಳಿ, ಅಥವಾ ಮೊದಲು ಸ್ಕ್ಯಾನ್ ಟ್ಯಾಬ್‌ನಲ್ಲಿ ಎಲೆಯನ್ನು ಪರೀಕ್ಷಿಸಿ.",
        "need_area": "ಎಷ್ಟು ಎಕರೆಗೆ ಸಿಂಪಡಿಸಬೇಕು? ಉದಾಹರಣೆಗೆ: '2 ಎಕರೆಗೆ ಪ್ರಮಾಣ'.",
        "no_products": "ಈ ಸಮಸ್ಯೆಗೆ ಔಷಧ ಪಟ್ಟಿ ಇಲ್ಲ. ದಯವಿಟ್ಟು ಚಿಕಿತ್ಸೆ ಸಲಹೆ ನೋಡಿ.",
        "dosage_result": "{name}, {area} ಎಕರೆ: ಸುಮಾರು {water} ಲೀ ನೀರು ({tank_l} ಲೀ ಟ್ಯಾಂಕ್ {tanks}). {items}. ಔಷಧ ಲೇಬಲ್ ಪಾಲಿಸಿ.",
        "inventory": "ನಿಮ್ಮ ಬಳಿ {qty} ಕ್ವಿಂಟಾಲ್ ದಾಸ್ತಾನು ಇದೆ, ಮೌಲ್ಯ ಸುಮಾರು ₹{value}. {soon} ಅನ್ನು ಬೇಗ ಮಾರಬೇಕು.",
        "inventory_empty": "ನಿಮ್ಮ ದಾಸ್ತಾನು ಪಟ್ಟಿ ಖಾಲಿ ಇದೆ. ಸ್ಟಾಕ್ ಟ್ಯಾಬ್‌ನಲ್ಲಿ ನಿಮ್ಮ ಫಸಲು ಸೇರಿಸಿ.",
        "market_info": "ಫೋಟೋ ಮತ್ತು ಬೆಲೆಯೊಂದಿಗೆ ನಿಮ್ಮ ಉತ್ಪನ್ನ ಪಟ್ಟಿ ಮಾಡಲು ಮಾರ್ಕೆಟ್ ಟ್ಯಾಬ್ ತೆರೆಯಿರಿ. ಖರೀದಿದಾರರು ವಿಚಾರಣೆ ಮೂಲಕ ಸಂಪರ್ಕಿಸುತ್ತಾರೆ.{count}",
        "market_count": " ಈಗ {n} ಸಕ್ರಿಯ ಪಟ್ಟಿಗಳಿವೆ.",
        "help": "ನಾನು ಬೆಳೆ ಬೆಲೆ, ಸಿಂಪಡಣೆ ಸಮಯ (ಹವಾಮಾನ), ರೋಗ ಚಿಕಿತ್ಸೆ, ಎಕರೆಗೆ ಪ್ರಮಾಣ, ನಿಮ್ಮ ದಾಸ್ತಾನು ಮತ್ತು ಮಾರುಕಟ್ಟೆಯಲ್ಲಿ ಸಹಾಯ ಮಾಡಬಲ್ಲೆ. ಕೆಳಗಿನ ಸಲಹೆಗಳನ್ನು ಪ್ರಯತ್ನಿಸಿ.",
        "suggestions": ["ಟೊಮೇಟೊ ಬೆಲೆ", "ಯಾವಾಗ ಸಿಂಪಡಿಸಬೇಕು?", "2 ಎಕರೆಗೆ ಪ್ರಮಾಣ", "ನನ್ನ ದಾಸ್ತಾನು"],
    },
}
ACRE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:acres?|एकड़|एकड|ಎಕರೆ)", re.IGNORECASE)


def detect_intent(text: str) -> str:
    for intent in ORDER:
        if any(k in text for k in KEYWORDS[intent]):
            return intent
    return "help"


def find_crop(db: Session, text: str) -> Crop | None:
    for c in db.query(Crop).all():
        names = [c.name.lower(), *[v.lower() for v in (c.local_names or {}).values()]]
        if any(n in text for n in names):
            return c
    return None


def find_disease(db: Session, text: str, crop: Crop | None) -> Disease | None:
    q = db.query(Disease).filter(Disease.is_healthy.is_(False))
    if crop:
        q = q.filter(Disease.crop_id == crop.id)
    for d in q.all():
        if d.name.lower() in text:
            return d
    return None


def last_scan_disease(db: Session, user: User) -> Disease | None:
    scan = (db.query(Scan).filter(Scan.user_id == user.id, Scan.uncertain.is_(False), Scan.disease_id.isnot(None))
            .order_by(Scan.created_at.desc()).first())
    return db.get(Disease, scan.disease_id) if scan else None


def _fmt_time(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%d %b %H:%M")


def answer(db: Session, user: User, text: str, lang: str) -> tuple[str, str]:
    R = REPLIES[lang]
    text = text.lower()
    intent = detect_intent(text)
    crop = find_crop(db, text)

    if intent == "price":
        if not crop:
            return R["need_crop"], intent
        markets = latest_by_market(db, crop.id)
        if not markets:
            return R["no_price"].format(crop=crop.name), intent
        m, best, _ = max(markets, key=lambda x: x[1])
        rows = (db.query(MandiPrice.modal_price).filter(MandiPrice.crop_id == crop.id, MandiPrice.market_id == m.id)
                .order_by(MandiPrice.date.desc()).limit(8).all())
        trend = R["trend"].format(chg=(rows[0][0] - rows[-1][0]) / rows[-1][0] * 100) if len(rows) == 8 else ""
        return R["price"].format(crop=crop.name, avg=round(latest_avg_price(db, crop.id)), market=m.name,
                                 best=round(best), trend=trend), intent

    if intent == "spray":
        if user.lat is None or user.lon is None:
            return R["need_location"], intent
        try:
            adv = weather.spray_advisory(user.lat, user.lon)
        except weather.WeatherUnavailable:
            return R["weather_down"], intent
        if adv["spray_now"]:
            msg = R["spray_good"].format(wind=adv["current"]["wind_kmh"], rain=adv["current"]["rain_prob"])
        else:
            reasons = ", ".join(R["r_" + r] for r in adv["reasons"]) or R["r_rain"]
            msg = R["spray_bad"].format(reasons=reasons)
            w = adv["next_window"]
            msg += R["next_window"].format(start=_fmt_time(w["start"]), end=_fmt_time(w["end"])) if w else R["no_window"]
        if adv["fungal_risk"] == "high":
            msg += R["fungal"]
        return msg, intent

    if intent == "dosage":
        disease = find_disease(db, text, crop) or last_scan_disease(db, user)
        m = ACRE_RE.search(text)
        if not m:
            return R["need_area"], intent
        if not disease:
            return R["no_last_scan"], intent
        if not disease.products:
            return R["no_products"], intent
        calc = dosage.calculate(disease.products, float(m.group(1)))
        items = "; ".join(f"{p['name']}: {p['quantity']:g} {p['unit']}" for p in calc["products"])
        return R["dosage_result"].format(name=disease.name, area=calc["area_acres"], water=calc["water_litres"],
                                         tanks=calc["tanks"], tank_l=calc["tank_litres"], items=items), intent

    if intent == "disease":
        disease = find_disease(db, text, crop)
        if disease is None:
            scan = (db.query(Scan).filter(Scan.user_id == user.id, Scan.uncertain.is_(False))
                    .order_by(Scan.created_at.desc()).first())
            disease = db.get(Disease, scan.disease_id) if scan and scan.disease_id else None
            if disease is not None and disease.is_healthy:
                return R["healthy"], intent
        if disease is None:
            return R["no_last_scan"], intent
        c = db.get(Crop, disease.crop_id)
        return R["disease_info"].format(name=disease.name, crop=c.name if c else "", sym=disease.symptoms,
                                        org=disease.organic_treatment or "-", chem=disease.chemical_treatment or "-",
                                        prev=disease.prevention), intent

    if intent == "inventory":
        items = db.query(InventoryItem).filter(InventoryItem.user_id == user.id).all()
        if not items:
            return R["inventory_empty"], intent
        cache: dict = {}
        out = [inventory_out(db, i, cache) for i in items]
        return R["inventory"].format(qty=round(sum(o.quantity_qtl for o in out), 1),
                                     value=round(sum(o.est_value or 0 for o in out)),
                                     soon=sum(o.sell_soon for o in out)), intent

    if intent == "market":
        n = db.query(Listing).filter(Listing.status == "active").count()
        return R["market_info"].format(count=R["market_count"].format(n=n) if n else ""), intent

    return R["help"], "help"


@router.post("/chat", response_model=ChatOut)
def chat(body: ChatIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    reply, intent = answer(db, user, body.message.strip(), body.language)
    return ChatOut(reply=reply, intent=intent, suggestions=REPLIES[body.language]["suggestions"])
