import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api.js";

export default function Prices({ t, crops, markets, cropName, user }) {
  const [cropId, setCropId] = useState("");
  const [marketId, setMarketId] = useState("");
  const [data, setData] = useState([]);
  const [fc, setFc] = useState(null);
  const [ranks, setRanks] = useState([]);
  const [err, setErr] = useState("");
  const [p, setP] = useState({ quantity_qtl: "", price_per_qtl: "", transport_cost: "", other_costs: "" });
  const [profit, setProfit] = useState(null);

  useEffect(() => { if (!cropId && crops.length) setCropId(String(crops[0].id)); }, [crops]);
  useEffect(() => { if (!marketId && markets.length) setMarketId(String(markets[0].id)); }, [markets]);

  useEffect(() => {
    if (!cropId || !marketId) return;
    setErr(""); setFc(null);
    Promise.all([api.prices(cropId, marketId, 60), api.forecast(cropId, marketId, 7).catch(() => null), api.bestMarket(cropId)])
      .then(([h, f, r]) => { setData(h); setFc(f); setRanks(r); if (h.length) setP((x) => ({ ...x, price_per_qtl: String(h[h.length - 1].modal_price) })); })
      .catch((e) => setErr(e.message));
  }, [cropId, marketId]);

  const chart = [
    ...data.map((d) => ({ date: d.date.slice(5), price: d.modal_price })),
    ...(fc ? fc.points.map((x) => ({ date: x.date.slice(5), forecast: x.predicted, lower: x.lower, upper: x.upper })) : []),
  ];
  const last = data[data.length - 1];

  const calc = async () => {
    try {
      setProfit(await api.profit({ quantity_qtl: +p.quantity_qtl, price_per_qtl: +p.price_per_qtl, transport_cost: +p.transport_cost || 0, other_costs: +p.other_costs || 0 }));
    } catch (e) { setErr(e.message); }
  };
  const adviceBadge = fc?.advice_key === "wait" ? "ok" : fc?.advice_key === "sell" ? "bad" : "warn";

  return (
    <>
      <div className="card">
        <div className="row">
          <div><label>{t("crop")}</label>
            <select value={cropId} onChange={(e) => setCropId(e.target.value)}>{crops.map((c) => <option key={c.id} value={c.id}>{cropName(c)}</option>)}</select></div>
          <div><label>{t("market")}</label>
            <select value={marketId} onChange={(e) => setMarketId(e.target.value)}>{markets.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></div>
        </div>
        {err && <div className="error">{err}</div>}
        {last && <p className="muted">{t("todayPrice")}: <span className="big">₹{Math.round(last.modal_price)}</span> ({last.date})</p>}
        <div style={{ width: "100%", height: 240 }}>
          <ResponsiveContainer>
            <LineChart data={chart} margin={{ left: -10, right: 8, top: 8 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="date" fontSize={12} minTickGap={24} />
              <YAxis fontSize={12} domain={["auto", "auto"]} />
              <Tooltip />
              <Line dataKey="price" stroke="#2f7d32" dot={false} strokeWidth={2} connectNulls />
              <Line dataKey="forecast" stroke="#e08a00" strokeDasharray="5 4" dot={false} strokeWidth={2} />
              <Line dataKey="lower" stroke="#e08a0088" dot={false} strokeWidth={1} />
              <Line dataKey="upper" stroke="#e08a0088" dot={false} strokeWidth={1} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        {fc && (
          <>
            <h3>{t("forecast")}</h3>
            <span className={`badge ${adviceBadge}`}>{t(`advice_${fc.advice_key}`)} ({fc.change_pct > 0 ? "+" : ""}{fc.change_pct}%)</span>
            <p className="muted">{fc.disclaimer} · {fc.method === "ml" ? "ML model" : "trend baseline"}</p>
          </>
        )}
      </div>

      <div className="card">
        <h2>{t("bestMarkets")}</h2>
        {user.lat == null && <p className="muted">{t("locationNeeded")}</p>}
        <table>
          <thead><tr><th>{t("market")}</th><th>₹</th><th>{t("distance")}</th><th>{t("net")}</th></tr></thead>
          <tbody>{ranks.map((r) => (
            <tr key={r.market_id}><td>{r.market}</td><td>{Math.round(r.price)}</td><td>{r.distance_km ?? "–"}</td><td><b>{Math.round(r.net_price)}</b></td></tr>
          ))}</tbody>
        </table>
      </div>

      <div className="card">
        <h2>{t("profit")}</h2>
        <div className="row">
          {[["quantity_qtl", "quantity"], ["price_per_qtl", "price"], ["transport_cost", "transport"], ["other_costs", "other"]].map(([k, label]) => (
            <div key={k}><label>{t(label)}</label><input inputMode="decimal" value={p[k]} onChange={(e) => setP({ ...p, [k]: e.target.value })} /></div>
          ))}
        </div>
        <p><button disabled={!+p.quantity_qtl || !+p.price_per_qtl} onClick={calc}>{t("calc")}</button></p>
        {profit && <p>{t("netProfit")}: <span className="big">₹{profit.net_profit.toLocaleString()}</span></p>}
      </div>
    </>
  );
}
