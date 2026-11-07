import { useEffect, useState } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import { api } from "../api.js";

export default function Outbreaks({ t }) {
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { api.outbreaks(30).then(setRows).catch((e) => setErr(e.message)); }, []);
  const max = Math.max(1, ...(rows || []).map((r) => r.count));
  const pts = (rows || []).filter((r) => r.lat != null && r.lon != null);
  const center = pts.length ? [pts[0].lat, pts[0].lon] : [15.3, 75.7]; // default: Karnataka

  return (
    <>
      <div className="card">
        <h2>🗺️ {t("mapTitle")}</h2>
        {rows && (
          <MapContainer center={center} zoom={pts.length ? 8 : 6} scrollWheelZoom={false}>
            <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
            {pts.map((r, i) => (
              <CircleMarker key={i} center={[r.lat, r.lon]} radius={8 + Math.min(r.count, 20) * 2}
                pathOptions={{ color: "#b3261e", fillColor: "#e05a4f", fillOpacity: 0.45 }}>
                <Popup><b>{r.disease}</b><br />{r.crop} · {r.district}<br />{r.count} {t("reports")}</Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        )}
        <p className="muted">{t("noCoords")}</p>
      </div>

      <div className="card">
        <h2>{t("outbreaks")}</h2>
        {err && <div className="error">{err}</div>}
        {rows && rows.length === 0 && <p className="muted">{t("noData")}</p>}
        {(rows || []).map((r, i) => (
          <div key={i} style={{ margin: "12px 0" }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <span><b>{r.disease}</b> {r.crop && <span className="muted">({r.crop})</span>}<br /><span className="muted">{r.district}</span></span>
              <span>{r.count} {t("reports")}</span>
            </div>
            <div className="bar" style={{ width: `${(r.count / max) * 100}%` }} />
          </div>
        ))}
      </div>
    </>
  );
}
