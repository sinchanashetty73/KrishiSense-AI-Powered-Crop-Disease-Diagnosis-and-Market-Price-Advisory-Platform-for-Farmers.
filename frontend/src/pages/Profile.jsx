import { useState } from "react";
import { api } from "../api.js";

export default function Profile({ t, user, setUser, onLogout }) {
  const [f, setF] = useState({ name: user.name || "", district: user.district || "", state: user.state || "", lat: user.lat, lon: user.lon });
  const [msg, setMsg] = useState("");

  const useLocation = () => navigator.geolocation?.getCurrentPosition((p) => setF((x) => ({ ...x, lat: p.coords.latitude, lon: p.coords.longitude })));
  const save = async () => { setUser(await api.updateMe(f)); setMsg(t("saved")); };

  return (
    <div className="card">
      <p className="muted">{user.phone}</p>
      <label>{t("name")}</label><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
      <label>{t("district")}</label><input value={f.district} onChange={(e) => setF({ ...f, district: e.target.value })} />
      <label>{t("state")}</label><input value={f.state} onChange={(e) => setF({ ...f, state: e.target.value })} />
      <p><button className="secondary" onClick={useLocation}>📍 {t("useLocation")}</button>
        {f.lat != null && <span className="muted"> {Number(f.lat).toFixed(3)}, {Number(f.lon).toFixed(3)}</span>}</p>
      <div className="row">
        <button onClick={save}>{t("save")}</button>
        <button className="secondary" onClick={onLogout}>{t("logout")}</button>
      </div>
      {msg && <p>{msg}</p>}
    </div>
  );
}
