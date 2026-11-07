import { useState } from "react";
import { api, setToken } from "../api.js";
import { LANGS } from "../i18n.js";

export default function Login({ t, lang, setLang, onDone }) {
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [devOtp, setDevOtp] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const run = async (fn) => { setBusy(true); setErr(""); try { await fn(); } catch (e) { setErr(e.message); } finally { setBusy(false); } };

  const requestOtp = () => run(async () => {
    const r = await api.requestOtp(phone.trim());
    setDevOtp(r.dev_otp || null);
    setSent(true);
  });
  const verify = () => run(async () => {
    const r = await api.verifyOtp(phone.trim(), code.trim(), name.trim() || null, lang);
    setToken(r.access_token);
    onDone(await api.me());
  });

  return (
    <div className="login">
      <div style={{ textAlign: "center", margin: "20px 0" }}>
        <div style={{ fontSize: 56 }}>🌱</div>
        <h1 style={{ margin: 0 }}>{t("appName")}</h1>
        <p className="muted">{t("tagline")}</p>
      </div>
      <div className="card">
        <label>{t("language")}</label>
        <select value={lang} onChange={(e) => setLang(e.target.value)}>
          {Object.entries(LANGS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <label>{t("phone")}</label>
        <input inputMode="numeric" placeholder="9876543210" value={phone} onChange={(e) => setPhone(e.target.value)} disabled={sent} />
        {!sent ? (
          <p><button disabled={busy || phone.trim().length < 10} onClick={requestOtp}>{t("getOtp")}</button></p>
        ) : (
          <>
            {devOtp && <div className="banner">Dev mode OTP: <b>{devOtp}</b></div>}
            <label>{t("name")}</label>
            <input value={name} onChange={(e) => setName(e.target.value)} />
            <label>{t("otp")}</label>
            <input inputMode="numeric" maxLength={6} value={code} onChange={(e) => setCode(e.target.value)} />
            <p><button disabled={busy || code.length !== 6} onClick={verify}>{t("verify")}</button></p>
          </>
        )}
        {err && <div className="error">{err}</div>}
      </div>
    </div>
  );
}
