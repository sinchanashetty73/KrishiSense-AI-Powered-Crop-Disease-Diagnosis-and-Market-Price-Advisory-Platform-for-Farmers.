import { useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip } from "react-leaflet";
import { api } from "../api.js";

const FALLBACK = { lat: 12.97, lon: 77.59 };
const COLORS = ["#e5484d", "#f5a524", "#46c15b", "#3e9bff", "#a06bff", "#8a9a8c"];

function sprayScore(w) {
  let s = 100;
  s -= Math.min(40, w.rain * 0.5);
  s -= w.wind > 15 ? 30 : w.wind > 10 ? 15 : 0;
  s -= w.temp > 35 ? 20 : w.temp > 32 ? 10 : 0;
  s -= w.hum > 85 ? 10 : 0;
  return Math.max(0, Math.round(s));
}

function Donut({ data, total, sel, setSel }) {
  const R = 70, C = 2 * Math.PI * R;
  let acc = 0;
  const cur = sel != null ? data[sel] : null;
  return (
    <div className="hd-donutwrap">
      <svg viewBox="0 0 200 200" className={`hd-donut ${cur ? "has-sel" : ""}`}>
        <circle cx="100" cy="100" r={R} fill="none" stroke="var(--line)" strokeWidth="26" style={{ opacity: 1, cursor: "default" }} />
        {data.map((d, i) => {
          const len = (d.value / total) * C;
          const el = (
            <circle key={d.name} className={sel === i ? "sel" : ""} cx="100" cy="100" r={R} fill="none"
              stroke={COLORS[i % COLORS.length]} strokeWidth={sel === i ? 34 : 26}
              strokeDasharray={`${len} ${C - len}`} strokeDashoffset={-acc}
              transform="rotate(-90 100 100)"
              onClick={() => setSel(sel === i ? null : i)} />
          );
          acc += len;
          return el;
        })}
      </svg>
      <div className="hd-center">
        {cur ? (
          <>
            <b style={{ color: COLORS[sel % COLORS.length] }}>{cur.value}</b>
            <small>{cur.name}<br />{Math.round((cur.value / total) * 100)}% of cases</small>
          </>
        ) : (
          <>
            <b>{total}</b>
            <small>total cases<br />tap a colour</small>
          </>
        )}
      </div>
    </div>
  );
}

export default function Home({ t, user, go }) {
  const [d, setD] = useState({});
  const [rows, setRows] = useState(null);
  const [w, setW] = useState(null);
  const [sel, setSel] = useState(null);

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

  useEffect(() => { api.outbreaks(30).then(setRows).catch(() => setRows([])); }, []);

  const lon = user.lon ?? user.lng ?? user.longitude;
  const pos = user.lat != null && lon != null ? { lat: user.lat, lon } : FALLBACK;

  useEffect(() => {
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${pos.lat}&longitude=${pos.lon}` +
      `&current=temperature_2m,relative_humidity_2m,wind_speed_10m` +
      `&hourly=precipitation_probability&forecast_days=1&timezone=auto`;
    fetch(url).then((r) => r.json()).then((x) =>
      setW({
        temp: x.current.temperature_2m,
        hum: x.current.relative_humidity_2m,
        wind: x.current.wind_speed_10m,
        rain: x.hourly.precipitation_probability[new Date().getHours()] ?? 0,
      })
    ).catch(() => {});
  }, [pos.lat, pos.lon]);

  const triggered = (d.alerts || []).filter((a) => a.triggered).length;
  const last = d.scans?.[0];

  const list = rows || [];
  const pts = list.filter((r) => r.lat != null && r.lon != null);
  const center = pts.length ? [pts[0].lat, pts[0].lon] : [pos.lat, pos.lon];
  const sevColor = (n) => (n >= 8 ? "#e5484d" : n >= 4 ? "#f5a524" : "#46c15b");

  const pie = useMemo(() => {
    const m = {};
    list.forEach((r) => { m[r.disease] = (m[r.disease] || 0) + r.count; });
    const arr = Object.entries(m).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);
    const top = arr.slice(0, 5);
    const rest = arr.slice(5).reduce((s, x) => s + x.value, 0);
    if (rest) top.push({ name: "Others", value: rest });
    return top;
  }, [rows]);
  const total = pie.reduce((s, x) => s + x.value, 0);

  const score = w ? sprayScore(w) : 0;
  const first = user.name ? `, ${user.name.split(" ")[0]}` : "";

  const actions = [
    ["scan", "📷", t("tabScan"), "Detect crop disease", "a1"],
    ["prices", "📈", t("tabPrices"), "Live market rates", "a2"],
    ["spray", "🧪", t("doseTitle"), "Dosage and weather advice", "a3"],
    ["market", "🛒", t("tabMarket"), "Buy and sell crops", "a4"],
    ["chat", "💬", t("tabChat"), "Ask in your language", "a5"],
  ];

  return (
    <div className="hd">
      <div className="hd-hello">
        <div>
          <h2>{t("welcome")}{first} 👋</h2>
          <span className="muted">{t("tagline")}</span>
        </div>
        {d.spray && (
          <span className={`badge ${d.spray.spray_now ? "ok" : "warn"}`} style={{ cursor: "pointer" }} onClick={() => go("spray")}>
            {d.spray.spray_now ? t("sprayGoodNow") : t("sprayNotNow")}
          </span>
        )}
      </div>

      <div className="hd-layout">
        <div className="hd-left">
          <div className="hd-stats">
            <div className="hd-stat" onClick={() => go("alerts")} style={{ cursor: "pointer" }}>
              <span className="muted">{t("alertsHit")}</span><b>{triggered}</b></div>
            <div className="hd-stat" onClick={() => go("stock")} style={{ cursor: "pointer" }}>
              <span className="muted">{t("sellSoonStock")}</span><b>{d.stock?.sell_soon_count ?? 0}</b></div>
            <div className="hd-stat" onClick={() => go("market")} style={{ cursor: "pointer" }}>
              <span className="muted">{t("openListings")}</span><b>{d.listings?.length ?? 0}</b></div>
            <div className="hd-stat">
              <span className="muted">Disease spots near you</span><b>{pts.length}</b></div>
          </div>

          <div className="hd-two">
            <div className="hd-box">
              <h3>🌦️ {t("sprayToday")}</h3>
              {w ? (
                <>
                  <div className="hd-temp">{Math.round(w.temp)}°C</div>
                  <div className="hd-gauge"><i style={{ left: `${Math.min(100, (w.temp / 45) * 100)}%` }} /></div>
                  <div className="hd-meters">
                    <div><span>💨 Wind</span><span className="muted">{w.wind} km/h</span>
                      <div className="hd-meter"><i style={{ width: `${Math.min(100, (w.wind / 25) * 100)}%` }} /></div></div>
                    <div><span>🌧️ Rain</span><span className="muted">{w.rain}%</span>
                      <div className="hd-meter"><i style={{ width: `${w.rain}%` }} /></div></div>
                    <div><span>💧 Humidity</span><span className="muted">{w.hum}%</span>
                      <div className="hd-meter"><i style={{ width: `${w.hum}%` }} /></div></div>
                  </div>
                  <p className="muted" style={{ margin: "10px 0 0" }}>Spray score: <b>{score}%</b></p>
                  {d.spray?.fungal_risk === "high" && <p className="muted">⚠️ {t("fungalHigh")}</p>}
                  {user.lat == null && <p className="muted">{t("setLocation")}</p>}
                </>
              ) : <p className="muted">…</p>}
            </div>

            <div className="hd-box">
              <h3>🦠 Diseases near you</h3>
              {total > 0 ? (
                <div className="hd-pie">
                  <Donut data={pie} total={total} sel={sel} setSel={setSel} />
                  <div className="hd-legend">
                    {pie.map((x, i) => (
                      <button key={x.name} className={sel === i ? "sel" : ""} onClick={() => setSel(sel === i ? null : i)}>
                        <i style={{ background: COLORS[i % COLORS.length] }} />
                        <span>{x.name}</span><b>{x.value}</b>
                      </button>
                    ))}
                  </div>
                </div>
              ) : <p className="muted">{rows ? t("noData") : "…"}</p>}
            </div>
          </div>

          <div className="hd-box">
            <h3>📷 {t("lastScan")}</h3>
            {last ? (
              <p style={{ margin: 0, fontSize: 19 }}>
                {last.uncertain ? "?" : last.predicted_label.replace(/___/g, " · ").replace(/_/g, " ")}
                {" · "}{Math.round(last.confidence * 100)}%
              </p>
            ) : <p className="muted" style={{ margin: 0 }}>{t("noScansYet")}</p>}
          </div>
        </div>

        <div className="hd-box hd-mapbox">
          <h3>🗺️ {t("mapTitle")}</h3>
          <MapContainer className="hd-map" center={center} zoom={pts.length ? 9 : 6} scrollWheelZoom={true} key={center.join(",")}>
            <TileLayer attribution="Tiles &copy; Esri"
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" />
            {pts.map((r, i) => (
              <CircleMarker key={i} center={[r.lat, r.lon]} radius={9 + Math.min(r.count, 20)}
                pathOptions={{ color: "#fff", weight: 2, fillColor: sevColor(r.count), fillOpacity: 0.85 }}>
                <Tooltip direction="top" className="dis-tip">{r.disease} · {r.count}</Tooltip>
                <Popup><b>{r.disease}</b><br />{r.crop} · {r.district}<br />{r.count} {t("reports")}</Popup>
              </CircleMarker>
            ))}
          </MapContainer>
          <p className="muted" style={{ margin: "8px 0 0" }}>🔴 High (8+) · 🟠 Medium (4-7) · 🟢 Low (1-3)</p>
        </div>
      </div>

      <h3 className="hd-h">{t("quickActions")}</h3>
      <div className="hd-actions">
        {actions.map(([id, icon, label, sub, cls]) => (
          <button key={id} className={`hd-act ${cls}`} onClick={() => go(id)}>
            <span className="hd-act-ico">{icon}</span>
            <b>{label}</b>
            <span>{sub}</span>
          </button>
        ))}
      </div>
    </div>
  );
}