import { useEffect, useState } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip } from "react-leaflet";
import { api } from "../api.js";

const TILES = {
  satellite: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr: "Tiles &copy; Esri",
  },
  street: {
    url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    attr: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  },
};

const sevColor = (n) => (n >= 8 ? "#e5484d" : n >= 4 ? "#f5a524" : "#46c15b");
const sevName = (n) => (n >= 8 ? "High" : n >= 4 ? "Medium" : "Low");

export default function Outbreaks({ t }) {
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState("");
  const [view, setView] = useState("satellite");

  useEffect(() => { api.outbreaks(30).then(setRows).catch((e) => setErr(e.message)); }, []);

  const list = rows || [];
  const max = Math.max(1, ...list.map((r) => r.count));
  const pts = list.filter((r) => r.lat != null && r.lon != null);
  const center = pts.length ? [pts[0].lat, pts[0].lon] : [15.3, 75.7]; // default: Karnataka
  const total = list.reduce((s, r) => s + r.count, 0);
  const high = list.filter((r) => r.count >= 8).length;
  const tile = TILES[view];

  return (
    <>
      {/* summary boxes */}
      <div className="dash-stats">
        <div className="stat"><span className="muted">Disease types</span><b>{list.length}</b></div>
        <div className="stat"><span className="muted">Total reports</span><b>{total}</b></div>
        <div className="stat"><span className="muted">High-risk spots</span><b>{high}</b></div>
        <div className="stat"><span className="muted">Mapped locations</span><b>{pts.length}</b></div>
      </div>

      {/* map */}
      <div className="card" style={{ borderRadius: 18 }}>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0 }}>🗺️ {t("mapTitle")}</h2>
          <div className="seg" style={{ margin: 0, flex: "0 0 auto" }}>
            <button className={view === "satellite" ? "on" : ""} onClick={() => setView("satellite")}>Satellite</button>
            <button className={view === "street" ? "on" : ""} onClick={() => setView("street")}>Street</button>
          </div>
        </div>

        {rows && (
          <MapContainer className="dash-map big-map" center={center} zoom={pts.length ? 8 : 6} scrollWheelZoom={true}>
            <TileLayer key={view} attribution={tile.attr} url={tile.url} />
            {pts.map((r, i) => (
              <CircleMarker key={i} center={[r.lat, r.lon]} radius={9 + Math.min(r.count, 20)}
                pathOptions={{ color: "#fff", weight: 2, fillColor: sevColor(r.count), fillOpacity: 0.85 }}>
                <Tooltip permanent direction="top" className="dis-tip">{r.disease} · {r.count}</Tooltip>
                <Popup><b>{r.disease}</b><br />{r.crop} · {r.district}<br />{r.count} {t("reports")}</Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        )}
        <p className="muted">🔴 High (8+) · 🟠 Medium (4-7) · 🟢 Low (1-3)</p>
        {rows && pts.length === 0 && <p className="muted">{t("noCoords")}</p>}
      </div>

      {/* list */}
      <div className="card" style={{ borderRadius: 18 }}>
        <h2>{t("outbreaks")}</h2>
        {err && <div className="error">{err}</div>}
        {rows && rows.length === 0 && <p className="muted">{t("noData")}</p>}
        <div className="outbreak-grid">
          {list.map((r, i) => (
            <div key={i} className="outbreak-item">
              <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
                <span>
                  <b>{r.disease}</b> {r.crop && <span className="muted">({r.crop})</span>}
                  <br /><span className="muted">{r.district}</span>
                </span>
                <span style={{ textAlign: "right", flex: "0 0 auto" }}>
                  <b>{r.count}</b> {t("reports")}<br />
                  <span className="badge" style={{ background: sevColor(r.count), color: "#fff" }}>{sevName(r.count)}</span>
                </span>
              </div>
              <div className="bar" style={{ width: `${(r.count / max) * 100}%`, background: sevColor(r.count), marginTop: 10 }} />
            </div>
          ))}
        </div>
      </div>
    </>
  );
}