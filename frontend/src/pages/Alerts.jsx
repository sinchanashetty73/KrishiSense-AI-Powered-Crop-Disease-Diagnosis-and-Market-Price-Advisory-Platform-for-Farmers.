import { useEffect, useState } from "react";
import { api } from "../api.js";
import { currentSubscription, disablePush, enablePush, pushSupported } from "../push.js";

const pct = (d) => d === "rise" || d === "fall";

export default function Alerts({ t, crops, markets, cropName }) {
  const [alerts, setAlerts] = useState([]);
  const [f, setF] = useState({ crop_id: "", market_id: "", direction: "above", threshold: "", notify_sms: true, notify_push: true });
  const [err, setErr] = useState("");
  const [info, setInfo] = useState("");
  const [pushOn, setPushOn] = useState(false);
  const load = () => api.alerts().then(setAlerts).catch((e) => setErr(e.message));
  useEffect(() => { load(); currentSubscription().then((s) => setPushOn(!!s)).catch(() => {}); }, []);
  useEffect(() => { setF((x) => ({ ...x, crop_id: x.crop_id || String(crops[0]?.id || ""), market_id: x.market_id || String(markets[0]?.id || "") })); }, [crops, markets]);

  const add = async () => {
    setErr("");
    try { await api.createAlert({ ...f, crop_id: +f.crop_id, market_id: +f.market_id, threshold: +f.threshold }); setF({ ...f, threshold: "" }); load(); }
    catch (e) { setErr(e.message); }
  };

  const togglePush = async () => {
    setErr(""); setInfo("");
    try {
      if (pushOn) { await disablePush(); setPushOn(false); return; }
      const r = await enablePush();
      if (r === "ok") setPushOn(true);
      else setErr(t({ unsupported: "pushUnsupported", denied: "pushDenied", not_configured: "pushNotConfigured" }[r]));
    } catch (e) { setErr(e.message); }
  };

  const test = async () => {
    setErr(""); setInfo("");
    try { await api.testAlert(); setInfo(t("testSent")); } catch (e) { setErr(e.message); }
  };

  const label = (a) => ({ above: t("above"), below: t("below"), rise: t("rise"), fall: t("fall") }[a.direction]);

  return (
    <>
      <div className="card">
        <h2>{t("newAlert")}</h2>
        <div className="row">
          <div><label>{t("crop")}</label><select value={f.crop_id} onChange={(e) => setF({ ...f, crop_id: e.target.value })}>{crops.map((c) => <option key={c.id} value={c.id}>{cropName(c)}</option>)}</select></div>
          <div><label>{t("market")}</label><select value={f.market_id} onChange={(e) => setF({ ...f, market_id: e.target.value })}>{markets.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></div>
        </div>
        <div className="row">
          <div><label>&nbsp;</label>
            <select value={f.direction} onChange={(e) => setF({ ...f, direction: e.target.value })}>
              <option value="above">{t("above")}</option><option value="below">{t("below")}</option>
              <option value="rise">{t("rise")}</option><option value="fall">{t("fall")}</option>
            </select></div>
          <div><label>{pct(f.direction) ? `${t("thresholdPct")} · ${t("inDays")}` : t("threshold")}</label>
            <input inputMode="numeric" value={f.threshold} onChange={(e) => setF({ ...f, threshold: e.target.value })} /></div>
        </div>
        <p>
          <label style={{ display: "inline-flex", gap: 6, marginRight: 16 }}><input type="checkbox" checked={f.notify_sms} onChange={(e) => setF({ ...f, notify_sms: e.target.checked })} /> {t("viaSms")}</label>
          <label style={{ display: "inline-flex", gap: 6 }}><input type="checkbox" checked={f.notify_push} onChange={(e) => setF({ ...f, notify_push: e.target.checked })} /> {t("viaPush")}</label>
        </p>
        <p className="muted">{t("alertHow")}</p>
        <p><button disabled={!+f.threshold || (!f.notify_sms && !f.notify_push)} onClick={add}>{t("add")}</button></p>
        {err && <div className="error">{err}</div>}
        {info && <div className="badge ok">{info}</div>}
      </div>

      {pushSupported() && (
        <div className="card">
          <div className="row" style={{ alignItems: "center" }}>
            <div>{pushOn ? t("pushOn") : t("enablePush")}</div>
            <button className="small" onClick={togglePush}>{pushOn ? t("pushOff") : "✓"}</button>
          </div>
        </div>
      )}
      <p><button className="secondary" onClick={test}>{t("sendTest")}</button></p>

      {alerts.map((a) => (
        <div className="card" key={a.id}>
          <div className="row" style={{ alignItems: "center" }}>
            <div><b>{a.crop}</b> · {a.market}<br />{label(a)} {pct(a.direction) ? `${a.threshold}% ${t("inDays")}` : `₹${a.threshold}`}
              <br /><span className="muted">{t("current")}: ₹{a.current_price ?? "–"}{a.change_pct != null && ` (${a.change_pct > 0 ? "+" : ""}${a.change_pct}%)`}</span>
              <br /><span className="muted">{[a.notify_sms && t("viaSms"), a.notify_push && t("viaPush")].filter(Boolean).join(" · ")}</span></div>
            {a.triggered && <span className="badge ok">{t("triggered")}</span>}
            <button className="small secondary" onClick={() => api.deleteAlert(a.id).then(load)}>✕</button>
          </div>
        </div>
      ))}
    </>
  );
}
