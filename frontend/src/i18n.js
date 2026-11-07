// Simple dictionary-based translations. TO CHANGE: add a language by adding a new key block;
// add UI text by adding the same key to every language (English is the fallback).
// Have a native speaker review the Hindi/Kannada text before real use.
import { extra } from "./i18nExtra.js";

export const LANGS = { en: "English", hi: "हिन्दी", kn: "ಕನ್ನಡ" };

const dict = {
  en: {
    appName: "KrishiSense", tagline: "Crop health and market prices, in one place",
    phone: "Mobile number", getOtp: "Get OTP", otp: "Enter OTP", verify: "Verify & continue",
    name: "Your name", logout: "Log out",
    tabScan: "Scan leaf", tabPrices: "Prices", tabAlerts: "Alerts", tabOutbreaks: "Nearby diseases", tabProfile: "Profile",
    crop: "Crop", market: "Market", anyCrop: "Not sure", takePhoto: "Take / choose leaf photo", analyse: "Check my crop",
    analysing: "Checking...", confidence: "Confidence", demoBanner: "Demo mode: the AI model is not trained yet, results are not real.",
    symptoms: "Symptoms", organic: "Organic treatment", chemical: "Chemical treatment", prevention: "Prevention",
    wasCorrect: "Was this correct?", yes: "Yes", no: "No", thanks: "Thanks for the feedback!",
    healthy: "Your plant looks healthy", history: "Recent scans",
    todayPrice: "Latest price (Rs/quintal)", forecast: "7-day forecast", advice_wait: "Likely to rise: consider waiting",
    advice_sell: "Likely to fall: consider selling soon", advice_stable: "Looks stable", range: "Range",
    bestMarkets: "Best markets for you", distance: "Distance", net: "After transport", locationNeeded: "Save your location in Profile for distance-based ranking.",
    profit: "Profit estimator", quantity: "Quantity (quintals)", price: "Price per quintal", transport: "Transport cost", other: "Other costs", calc: "Calculate", netProfit: "Net profit",
    newAlert: "New price alert", above: "goes above", below: "falls below", threshold: "Price (Rs)", add: "Add alert", triggered: "Triggered!", current: "Now",
    outbreaks: "Disease reports near you (last 30 days)", noData: "No data yet.", reports: "reports",
    district: "District", state: "State", save: "Save", useLocation: "Use my current location", saved: "Saved",
    loading: "Loading...", error: "Something went wrong", language: "Language",
  },
  hi: {
    appName: "कृषिसेंस", tagline: "फसल का स्वास्थ्य और मंडी भाव, एक जगह",
    phone: "मोबाइल नंबर", getOtp: "OTP पाएँ", otp: "OTP दर्ज करें", verify: "सत्यापित करें", name: "आपका नाम", logout: "लॉग आउट",
    tabScan: "पत्ती जाँचें", tabPrices: "भाव", tabAlerts: "अलर्ट", tabOutbreaks: "आस-पास के रोग", tabProfile: "प्रोफ़ाइल",
    crop: "फसल", market: "मंडी", anyCrop: "पता नहीं", takePhoto: "पत्ती की फोटो लें / चुनें", analyse: "मेरी फसल जाँचें",
    analysing: "जाँच हो रही है...", confidence: "भरोसा", demoBanner: "डेमो मोड: AI मॉडल अभी प्रशिक्षित नहीं है, नतीजे असली नहीं हैं।",
    symptoms: "लक्षण", organic: "जैविक उपचार", chemical: "रासायनिक उपचार", prevention: "बचाव",
    wasCorrect: "क्या यह सही था?", yes: "हाँ", no: "नहीं", thanks: "प्रतिक्रिया के लिए धन्यवाद!",
    healthy: "आपका पौधा स्वस्थ दिखता है", history: "पिछली जाँचें",
    todayPrice: "ताज़ा भाव (रु/क्विंटल)", forecast: "7 दिन का अनुमान", advice_wait: "भाव बढ़ सकते हैं: रुकने पर विचार करें",
    advice_sell: "भाव गिर सकते हैं: जल्दी बेचने पर विचार करें", advice_stable: "भाव स्थिर दिखते हैं", range: "सीमा",
    bestMarkets: "आपके लिए सबसे अच्छी मंडियाँ", distance: "दूरी", net: "ढुलाई के बाद", locationNeeded: "दूरी के आधार पर क्रम के लिए प्रोफ़ाइल में अपना स्थान सहेजें।",
    profit: "मुनाफ़ा कैलकुलेटर", quantity: "मात्रा (क्विंटल)", price: "भाव प्रति क्विंटल", transport: "ढुलाई खर्च", other: "अन्य खर्च", calc: "गणना करें", netProfit: "शुद्ध मुनाफ़ा",
    newAlert: "नया भाव अलर्ट", above: "से ऊपर जाए", below: "से नीचे जाए", threshold: "भाव (रु)", add: "अलर्ट जोड़ें", triggered: "सक्रिय!", current: "अभी",
    outbreaks: "आपके पास रोग की रिपोर्ट (पिछले 30 दिन)", noData: "अभी कोई डेटा नहीं।", reports: "रिपोर्ट",
    district: "जिला", state: "राज्य", save: "सहेजें", useLocation: "मेरा वर्तमान स्थान उपयोग करें", saved: "सहेजा गया",
    loading: "लोड हो रहा है...", error: "कुछ गलत हो गया", language: "भाषा",
  },
  kn: {
    appName: "ಕೃಷಿಸೆನ್ಸ್", tagline: "ಬೆಳೆ ಆರೋಗ್ಯ ಮತ್ತು ಮಾರುಕಟ್ಟೆ ಬೆಲೆ, ಒಂದೇ ಸ್ಥಳದಲ್ಲಿ",
    phone: "ಮೊಬೈಲ್ ಸಂಖ್ಯೆ", getOtp: "OTP ಪಡೆಯಿರಿ", otp: "OTP ನಮೂದಿಸಿ", verify: "ಪರಿಶೀಲಿಸಿ", name: "ನಿಮ್ಮ ಹೆಸರು", logout: "ಲಾಗ್ ಔಟ್",
    tabScan: "ಎಲೆ ಪರೀಕ್ಷೆ", tabPrices: "ಬೆಲೆ", tabAlerts: "ಎಚ್ಚರಿಕೆ", tabOutbreaks: "ಸುತ್ತಮುತ್ತಲಿನ ರೋಗ", tabProfile: "ಪ್ರೊಫೈಲ್",
    crop: "ಬೆಳೆ", market: "ಮಾರುಕಟ್ಟೆ", anyCrop: "ಗೊತ್ತಿಲ್ಲ", takePhoto: "ಎಲೆಯ ಫೋಟೋ ತೆಗೆಯಿರಿ / ಆಯ್ಕೆಮಾಡಿ", analyse: "ನನ್ನ ಬೆಳೆ ಪರೀಕ್ಷಿಸಿ",
    analysing: "ಪರೀಕ್ಷಿಸಲಾಗುತ್ತಿದೆ...", confidence: "ವಿಶ್ವಾಸ", demoBanner: "ಡೆಮೊ ಮೋಡ್: AI ಮಾದರಿ ಇನ್ನೂ ತರಬೇತಿ ಪಡೆದಿಲ್ಲ, ಫಲಿತಾಂಶ ನಿಜವಲ್ಲ.",
    symptoms: "ಲಕ್ಷಣಗಳು", organic: "ಸಾವಯವ ಚಿಕಿತ್ಸೆ", chemical: "ರಾಸಾಯನಿಕ ಚಿಕಿತ್ಸೆ", prevention: "ತಡೆಗಟ್ಟುವಿಕೆ",
    wasCorrect: "ಇದು ಸರಿಯಾಗಿತ್ತೇ?", yes: "ಹೌದು", no: "ಇಲ್ಲ", thanks: "ಪ್ರತಿಕ್ರಿಯೆಗೆ ಧನ್ಯವಾದಗಳು!",
    healthy: "ನಿಮ್ಮ ಸಸ್ಯ ಆರೋಗ್ಯವಾಗಿ ಕಾಣುತ್ತಿದೆ", history: "ಇತ್ತೀಚಿನ ಪರೀಕ್ಷೆಗಳು",
    todayPrice: "ಇತ್ತೀಚಿನ ಬೆಲೆ (ರೂ/ಕ್ವಿಂಟಾಲ್)", forecast: "7 ದಿನದ ಮುನ್ಸೂಚನೆ", advice_wait: "ಬೆಲೆ ಏರಬಹುದು: ಕಾಯುವುದನ್ನು ಪರಿಗಣಿಸಿ",
    advice_sell: "ಬೆಲೆ ಇಳಿಯಬಹುದು: ಬೇಗ ಮಾರುವುದನ್ನು ಪರಿಗಣಿಸಿ", advice_stable: "ಬೆಲೆ ಸ್ಥಿರವಾಗಿದೆ", range: "ವ್ಯಾಪ್ತಿ",
    bestMarkets: "ನಿಮಗೆ ಉತ್ತಮ ಮಾರುಕಟ್ಟೆಗಳು", distance: "ದೂರ", net: "ಸಾಗಣೆ ನಂತರ", locationNeeded: "ದೂರದ ಆಧಾರದ ಶ್ರೇಣಿಗಾಗಿ ಪ್ರೊಫೈಲ್‌ನಲ್ಲಿ ಸ್ಥಳ ಉಳಿಸಿ.",
    profit: "ಲಾಭ ಕ್ಯಾಲ್ಕುಲೇಟರ್", quantity: "ಪ್ರಮಾಣ (ಕ್ವಿಂಟಾಲ್)", price: "ಕ್ವಿಂಟಾಲ್‌ಗೆ ಬೆಲೆ", transport: "ಸಾಗಣೆ ವೆಚ್ಚ", other: "ಇತರ ವೆಚ್ಚ", calc: "ಲೆಕ್ಕ ಹಾಕಿ", netProfit: "ನಿವ್ವಳ ಲಾಭ",
    newAlert: "ಹೊಸ ಬೆಲೆ ಎಚ್ಚರಿಕೆ", above: "ಮೇಲೆ ಹೋದರೆ", below: "ಕೆಳಗೆ ಇಳಿದರೆ", threshold: "ಬೆಲೆ (ರೂ)", add: "ಎಚ್ಚರಿಕೆ ಸೇರಿಸಿ", triggered: "ಸಕ್ರಿಯ!", current: "ಈಗ",
    outbreaks: "ನಿಮ್ಮ ಹತ್ತಿರ ರೋಗ ವರದಿಗಳು (ಕಳೆದ 30 ದಿನ)", noData: "ಇನ್ನೂ ಮಾಹಿತಿ ಇಲ್ಲ.", reports: "ವರದಿಗಳು",
    district: "ಜಿಲ್ಲೆ", state: "ರಾಜ್ಯ", save: "ಉಳಿಸಿ", useLocation: "ನನ್ನ ಪ್ರಸ್ತುತ ಸ್ಥಳ ಬಳಸಿ", saved: "ಉಳಿಸಲಾಗಿದೆ",
    loading: "ಲೋಡ್ ಆಗುತ್ತಿದೆ...", error: "ಏನೋ ತಪ್ಪಾಗಿದೆ", language: "ಭಾಷೆ",
  },
};

export function makeT(lang) {
  // Lookup order: current language, then English, so a missing translation never shows a raw key.
  return (key) => dict[lang]?.[key] ?? extra[lang]?.[key] ?? dict.en[key] ?? extra.en[key] ?? key;
}
