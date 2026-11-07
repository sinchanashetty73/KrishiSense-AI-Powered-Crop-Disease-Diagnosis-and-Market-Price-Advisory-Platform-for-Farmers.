import { useEffect, useMemo, useState } from "react";
import { api, getToken, setToken } from "./api.js";
import { LANGS, makeT } from "./i18n.js";
import Login from "./pages/Login.jsx";
import Home from "./pages/Home.jsx";
import Scan from "./pages/Scan.jsx";
import Spray from "./pages/Spray.jsx";
import Prices from "./pages/Prices.jsx";
import Market from "./pages/Market.jsx";
import Stock from "./pages/Stock.jsx";
import Chat from "./pages/Chat.jsx";
import Alerts from "./pages/Alerts.jsx";
import Outbreaks from "./pages/Outbreaks.jsx";
import Profile from "./pages/Profile.jsx";

// TO CHANGE: add a page by adding it here, to PAGES below, and creating src/pages/<Name>.jsx
const TABS = [["home", "tabHome"], ["scan", "tabScan"], ["spray", "tabSpray"], ["prices", "tabPrices"], ["market", "tabMarket"],
  ["stock", "tabStock"], ["chat", "tabChat"], ["alerts", "tabAlerts"], ["outbreaks", "tabOutbreaks"], ["profile", "tabProfile"]];
const PAGES = { home: Home, scan: Scan, spray: Spray, prices: Prices, market: Market, stock: Stock, chat: Chat,
  alerts: Alerts, outbreaks: Outbreaks, profile: Profile };

export default function App() {
  const [lang, setLang] = useState(localStorage.getItem("ks_lang") || "en");
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const [tab, setTab] = useState("home");
  const [params, setParams] = useState({});
  const [crops, setCrops] = useState([]);
  const [markets, setMarkets] = useState([]);
  const t = useMemo(() => makeT(lang), [lang]);

  const go = (next, p = {}) => { setParams(p); setTab(next); window.scrollTo(0, 0); };
  const changeLang = (l) => { setLang(l); localStorage.setItem("ks_lang", l); if (user) api.updateMe({ language: l }).catch(() => {}); };

  useEffect(() => {
    const out = () => setUser(null);
    window.addEventListener("ks-logout", out);
    return () => window.removeEventListener("ks-logout", out);
  }, []);

  useEffect(() => {
    if (!getToken()) { setReady(true); return; }
    api.me().then((u) => { setUser(u); if (u.language) setLang(u.language); }).catch(() => {}).finally(() => setReady(true));
  }, []);

  useEffect(() => {
    if (user) { api.crops().then(setCrops).catch(() => {}); api.markets().then(setMarkets).catch(() => {}); }
  }, [user]);

  if (!ready) return <div className="app"><p>…</p></div>;
  if (!user) return (
    <div className="app">
      <Login t={t} lang={lang} setLang={changeLang} onDone={(u) => setUser(u)} />
    </div>
  );

  const cropName = (c) => c.local_names?.[lang] || c.name;
  const shared = { t, lang, user, crops, markets, cropName, go, params };
  const Page = PAGES[tab];

  return (
    <div className="app">
      <header className="top">
        <h1>🌱 {t("appName")}</h1>
        <select aria-label={t("language")} value={lang} onChange={(e) => changeLang(e.target.value)} style={{ width: "auto" }}>
          {Object.entries(LANGS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </header>

      <Page key={tab + JSON.stringify(params)} {...shared} setUser={setUser} onLogout={() => { setToken(null); setUser(null); }} />

      <nav className="tabs"><div className="inner">
        {TABS.map(([id, label]) => (
          <button key={id} className={tab === id ? "active" : ""} onClick={() => go(id)}>{t(label)}</button>
        ))}
      </div></nav>
    </div>
  );
}
