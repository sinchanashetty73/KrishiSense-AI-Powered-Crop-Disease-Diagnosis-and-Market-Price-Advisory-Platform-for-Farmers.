import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Home({ t, user, go }) {
  const [d, setD] = useState({});

  useEffect(() => {
    const tasks = {
      alerts: api.alerts(),
      stock: api.inventory(),
      scans: api.scans(),
      listings: api.listings(),
      spray: user.lat != null ? api.spray() : Promise.reject(new Error("no-location")),
    };
    Promise.allSettled(Object.values(tasks)).then((res) => {
      const out = {};
      Object.keys(tasks).forEach((k, i) => { if (res[i].status === "fulfilled") out[k] = res[i].value; });
      setD(out);
    });
  }, []);

  const triggered = (d.alerts || []).filter((a) => a.triggered).length;
  const last = d.scans?.[0];

  return (
    <>
      <div className="card">
        <h2>{t("welcome")}{user.name ? `, ${user.name.split(" ")[0]}` : ""} 👋</h2>
        <p className="muted">{t("tagline")}</p>
      </div>

      <div className="card" onClick={() => go("spray")} style={{ cursor: "pointer" }}>
        <h3 style={{ marginTop: 0 }}>🌦️ {t("sprayToday")}</h3>
        {d.spray ? (
          <>
            <span className={`badge ${d.spray.spray_now ? "ok" : "warn"}`}>{d.spray.spray_now ? t("sprayGoodNow") : t("sprayNotNow")}</span>
            {d.spray.fungal_risk === "high" && <p className="muted">⚠️ {t("fungalHigh")}</p>}
          </>
        ) : <p className="muted">{user.lat == null ? t("setLocation") : "…"}</p>}
      </div>

      <div className="grid2">
        <div className="stat" onClick={() => go("alerts")} style={{ cursor: "pointer" }}><b>{triggered}</b><span className="muted">{t("alertsHit")}</span></div>
        <div className="stat" onClick={() => go("stock")} style={{ cursor: "pointer" }}><b>{d.stock?.sell_soon_count ?? 0}</b><span className="muted">{t("sellSoonStock")}</span></div>
        <div className="stat" onClick={() => go("market")} style={{ cursor: "pointer" }}><b>{d.listings?.length ?? 0}</b><span className="muted">{t("openListings")}</span></div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>{t("lastScan")}</h3>
        {last ? (
          <p>{last.uncertain ? "?" : last.predicted_label.replace(/___/g, " · ").replace(/_/g, " ")} · {Math.round(last.confidence * 100)}%</p>
        ) : <p className="muted">{t("noScansYet")}</p>}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>{t("quickActions")}</h3>
        <div className="chips">
          <button className="chip" onClick={() => go("scan")}>📷 {t("tabScan")}</button>
          <button className="chip" onClick={() => go("prices")}>📈 {t("tabPrices")}</button>
          <button className="chip" onClick={() => go("spray")}>🧪 {t("doseTitle")}</button>
          <button className="chip" onClick={() => go("market")}>🛒 {t("tabMarket")}</button>
          <button className="chip" onClick={() => go("chat")}>💬 {t("tabChat")}</button>
        </div>
      </div>
    </>
  );
}
