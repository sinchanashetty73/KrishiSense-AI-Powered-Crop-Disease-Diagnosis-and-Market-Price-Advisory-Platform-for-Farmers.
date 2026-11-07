import { useEffect, useState } from "react";
import { api } from "../api.js";
import { speak } from "./Chat.jsx";

export default function Scan({ t, lang, crops, cropName, go }) {
  const [cropId, setCropId] = useState("");
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [fb, setFb] = useState(false);
  const [err, setErr] = useState("");
  const [history, setHistory] = useState([]);

  const loadHistory = () => api.scans().then(setHistory).catch(() => {});
  useEffect(() => { loadHistory(); }, []);
  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview]);

  const pick = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setFile(f); setPreview(URL.createObjectURL(f)); setResult(null); setFb(false); setErr("");
  };

  const submit = async () => {
    setBusy(true); setErr(""); setResult(null); setFb(false);
    try {
      const coords = await new Promise((res) => {
        if (!navigator.geolocation) return res(null);
        navigator.geolocation.getCurrentPosition((p) => res(p.coords), () => res(null), { timeout: 4000 });
      });
      setResult(await api.scan(file, cropId, coords));
      loadHistory();
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };

  const sendFeedback = async (correct) => { await api.feedback(result.id, correct).catch(() => {}); setFb(true); };
  const d = result?.disease;
  const summary = d ? `KrishiSense: ${d.name}. ${d.organic_treatment} ${d.chemical_treatment}`.trim() : "";

  return (
    <>
      <div className="card">
        <label>{t("crop")}</label>
        <select value={cropId} onChange={(e) => setCropId(e.target.value)}>
          <option value="">{t("anyCrop")}</option>
          {crops.map((c) => <option key={c.id} value={c.id}>{cropName(c)}</option>)}
        </select>
        <label>{t("takePhoto")}</label>
        <input type="file" accept="image/*" capture="environment" onChange={pick} />
        {preview && <img className="preview" src={preview} alt="leaf" />}
        <p><button disabled={!file || busy} onClick={submit}>{busy ? t("analysing") : t("analyse")}</button></p>
        {err && <div className="error">{err}</div>}
        {!preview && (
          <details>
            <summary>📷 {t("guideTitle")}</summary>
            <ul><li>{t("tip1")}</li><li>{t("tip2")}</li><li>{t("tip3")}</li><li>{t("tip4")}</li></ul>
          </details>
        )}
      </div>

      {result && (
        <div className="card">
          {result.demo && <div className="banner">{t("demoBanner")}</div>}
          {result.uncertain ? (
            <>
              <span className="badge warn">?</span>
              <p>{result.message}</p>
              <details open><summary>📷 {t("guideTitle")}</summary>
                <ul><li>{t("tip1")}</li><li>{t("tip2")}</li><li>{t("tip3")}</li><li>{t("tip4")}</li></ul></details>
            </>
          ) : d?.is_healthy ? (
            <h2>✅ {t("healthy")}</h2>
          ) : d ? (
            <>
              <h2>{d.name}</h2>
              <span className={`badge ${result.confidence > 0.8 ? "ok" : "warn"}`}>{t("confidence")}: {Math.round(result.confidence * 100)}%</span>
              {result.top?.length > 1 && (
                <p className="muted">{result.top.slice(1).map((x) => `${x.label.replace(/___/g, " · ").replace(/_/g, " ")} ${Math.round(x.confidence * 100)}%`).join(" · ")}</p>
              )}
              {d.symptoms && <><h3>{t("symptoms")}</h3><div>{d.symptoms}</div></>}
              {d.organic_treatment && <><h3>{t("organic")}</h3><div>{d.organic_treatment}</div></>}
              {d.chemical_treatment && <><h3>{t("chemical")}</h3><div>{d.chemical_treatment}</div></>}
              {d.prevention && <><h3>{t("prevention")}</h3><div>{d.prevention}</div></>}
              <p className="chips">
                <button className="chip" onClick={() => go("spray", { diseaseId: d.id })}>🧪 {t("calcDose")}</button>
                <button className="chip" onClick={() => speak(`${d.name}. ${d.organic_treatment}`, lang)}>🔊 {t("readAloud")}</button>
                <a className="chip" style={{ textDecoration: "none", display: "inline-block" }} target="_blank" rel="noreferrer"
                  href={`https://wa.me/?text=${encodeURIComponent(summary)}`}>💬 {t("shareWhatsApp")}</a>
              </p>
            </>
          ) : (
            <p>{result.label} ({Math.round(result.confidence * 100)}%)</p>
          )}
          <p className="muted">{result.disclaimer}</p>
          {fb ? <p>{t("thanks")}</p> : (
            <div className="row" style={{ alignItems: "center" }}>
              <span>{t("wasCorrect")}</span>
              <button className="small" onClick={() => sendFeedback(true)}>{t("yes")}</button>
              <button className="small secondary" onClick={() => sendFeedback(false)}>{t("no")}</button>
            </div>
          )}
        </div>
      )}

      {history.length > 0 && (
        <div className="card">
          <h2>{t("history")}</h2>
          <table><tbody>
            {history.slice(0, 8).map((h) => (
              <tr key={h.id}>
                <td>{new Date(h.created_at + "Z").toLocaleDateString()}</td>
                <td>{h.uncertain ? "?" : h.predicted_label.replace(/___/g, " · ").replace(/_/g, " ")}</td>
                <td>{Math.round(h.confidence * 100)}%</td>
              </tr>
            ))}
          </tbody></table>
        </div>
      )}
    </>
  );
}
