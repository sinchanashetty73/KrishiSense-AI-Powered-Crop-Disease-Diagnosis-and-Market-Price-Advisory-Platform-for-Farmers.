import { useEffect, useState } from "react";
import { api } from "../api.js";

const fmt = (iso) => {
  const d = new Date(iso);  // forecast times are the farm's local time
  return d.toLocaleDateString([], { weekday: "short" }) + " " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
};

export default function Spray({ t, params }) {
  const [adv, setAdv] = useState(null);
  const [advErr, setAdvErr] = useState("");
  const [diseases, setDiseases] = useState([]);
  const [diseaseId, setDiseaseId] = useState(params.diseaseId ? String(params.diseaseId) : "");
  const [area, setArea] = useState("1");
  const [vol, setVol] = useState("");
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.spray().then(setAdv).catch((e) => setAdvErr(e.message));
    api.diseases().then((r) => setDiseases(r.filter((d) => d.has_products))).catch(() => {});
  }, []);

  const calc = async () => {
    setErr(""); setRes(null);
    try {
      setRes(await api.dosage({ disease_id: +diseaseId, area_acres: +area, spray_volume_l_per_acre: vol ? +vol : null }));
    } catch (e) { setErr(e.message); }
  };

  return (
    <>
      <div className="card">
        <h2>🌦️ {t("sprayTitle")}</h2>
        {advErr && <div className="error">{advErr}</div>}
        {adv && (
          <>
            <span className={`badge ${adv.spray_now ? "ok" : "warn"}`}>
              {adv.spray_now ? t("sprayGoodNow") : `${t("sprayNotNow")} (${adv.reasons.map((r) => t("reason_" + r)).join(", ")})`}
            </span>
            {adv.current && (
              <p className="muted">{t("now")}: {t("temperature")} {adv.current.temp_c}°C · {t("windKmh")} {adv.current.wind_kmh} km/h · {t("rainChance")} {adv.current.rain_prob}%</p>
            )}
            <h3>{t("nextWindows")}</h3>
            {adv.windows.length === 0 ? <p>{t("noWindows")}</p> : (
              <table><tbody>
                {adv.windows.map((w) => (
                  <tr key={w.start}><td>{fmt(w.start)} – {new Date(w.end).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</td>
                    <td>{w.hours} {t("hours")}</td><td>{w.avg_wind_kmh} km/h</td></tr>
                ))}
              </tbody></table>
            )}
            <p>{adv.fungal_risk === "high" ? `⚠️ ${t("fungalHigh")}` : `✅ ${t("fungalLow")}`}</p>
            <p className="muted">{t("rulesNote").replace("{w}", adv.rules.max_wind_kmh).replace("{r}", adv.rules.max_rain_prob)
              .replace("{h}", adv.rules.rain_free_hours).replace("{t}", adv.rules.max_temp_c)}</p>
          </>
        )}
      </div>

      <div className="card">
        <h2>🧪 {t("doseTitle")}</h2>
        <label>{t("disease")}</label>
        <select value={diseaseId} onChange={(e) => setDiseaseId(e.target.value)}>
          <option value="">{t("chooseDisease")}</option>
          {diseases.map((d) => <option key={d.id} value={d.id}>{d.crop} – {d.name}</option>)}
        </select>
        <div className="row">
          <div><label>{t("area")}</label><input inputMode="decimal" value={area} onChange={(e) => setArea(e.target.value)} /></div>
          <div><label>{t("sprayVolume")}</label><input inputMode="decimal" placeholder="200" value={vol} onChange={(e) => setVol(e.target.value)} /></div>
        </div>
        <p><button disabled={!diseaseId || !+area} onClick={calc}>{t("calc")}</button></p>
        {err && <div className="error">{err}</div>}
        {res && (
          <>
            <p>{t("waterNeeded")}: <b>{res.water_litres} L</b> ({res.tanks} {t("tanks")} × {res.tank_litres} L)</p>
            <table>
              <thead><tr><th>{t("product")}</th><th>{t("quantity")}</th><th>{t("perTank")}</th></tr></thead>
              <tbody>{res.products.map((p) => (
                <tr key={p.name}><td>{p.name}<br /><span className={`badge ${p.kind === "organic" ? "ok" : "warn"}`}>{p.kind === "organic" ? t("organic") : t("chemical")}</span></td>
                  <td><b>{p.quantity} {p.unit}</b></td><td>{p.per_tank} {p.unit}</td></tr>
              ))}</tbody>
            </table>
            <div className="banner">{res.disclaimer}</div>
          </>
        )}
      </div>
    </>
  );
}
