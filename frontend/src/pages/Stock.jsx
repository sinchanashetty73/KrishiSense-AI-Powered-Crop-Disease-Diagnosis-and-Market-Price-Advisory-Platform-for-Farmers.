import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Stock({ t, crops, cropName, go }) {
  const today = new Date().toISOString().slice(0, 10);
  const [data, setData] = useState({ items: [], total_qtl: 0, total_value: 0, sell_soon_count: 0 });
  const [f, setF] = useState({ crop_id: "", quantity_qtl: "", harvest_date: today, storage_location: "", notes: "" });
  const [err, setErr] = useState("");

  const load = () => api.inventory().then(setData).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  useEffect(() => { if (!f.crop_id && crops.length) setF((x) => ({ ...x, crop_id: String(crops[0].id) })); }, [crops]);

  const add = async () => {
    setErr("");
    try { await api.addStock({ ...f, crop_id: +f.crop_id, quantity_qtl: +f.quantity_qtl, storage_location: f.storage_location || null, notes: f.notes || null }); setF({ ...f, quantity_qtl: "", notes: "" }); load(); }
    catch (e) { setErr(e.message); }
  };

  return (
    <>
      <div className="grid2">
        <div className="stat"><b>{data.total_qtl}</b><span className="muted">{t("totalStock")} ({t("quintals")})</span></div>
        <div className="stat"><b>₹{Math.round(data.total_value).toLocaleString()}</b><span className="muted">{t("totalValue")}</span></div>
        <div className="stat"><b>{data.sell_soon_count}</b><span className="muted">{t("sellSoonStock")}</span></div>
      </div>

      <div className="card">
        <h2>{t("addStock")}</h2>
        <div className="row">
          <div><label>{t("crop")}</label><select value={f.crop_id} onChange={(e) => setF({ ...f, crop_id: e.target.value })}>{crops.map((c) => <option key={c.id} value={c.id}>{cropName(c)}</option>)}</select></div>
          <div><label>{t("qtyQtl")}</label><input inputMode="decimal" value={f.quantity_qtl} onChange={(e) => setF({ ...f, quantity_qtl: e.target.value })} /></div>
        </div>
        <div className="row">
          <div><label>{t("harvestDate")}</label><input type="date" max={today} value={f.harvest_date} onChange={(e) => setF({ ...f, harvest_date: e.target.value })} /></div>
          <div><label>{t("storage")}</label><input maxLength={120} value={f.storage_location} onChange={(e) => setF({ ...f, storage_location: e.target.value })} /></div>
        </div>
        <label>{t("notes")}</label><input maxLength={300} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} />
        <p><button disabled={!+f.quantity_qtl || !f.harvest_date} onClick={add}>{t("add")}</button></p>
        {err && <div className="error">{err}</div>}
      </div>

      {data.items.length === 0 && <p className="muted">{t("emptyStock")}</p>}
      {data.items.map((i) => (
        <div className="card" key={i.id}>
          <div className="row" style={{ alignItems: "center" }}>
            <div><b>{i.crop}</b> · {i.quantity_qtl} {t("quintals")}
              {i.storage_location && <span className="muted"> · {i.storage_location}</span>}
              <br /><span className="muted">{i.days_stored} {t("daysStored")}{i.shelf_life_days ? ` / ${i.shelf_life_days} (${t("shelfLife")})` : ""}</span>
              {i.est_value != null && <><br />{t("estValue")}: ₹{Math.round(i.est_value).toLocaleString()}</>}
              {i.notes && <><br /><span className="muted">{i.notes}</span></>}</div>
            {i.sell_soon && <span className="badge bad">{t("sellSoon")}</span>}
          </div>
          <p>
            <button className="small" onClick={() => go("market", { prefill: { crop_id: i.crop_id, quantity: i.quantity_qtl } })}>{t("sellOnMarket")}</button>{" "}
            <button className="small secondary" onClick={() => api.deleteStock(i.id).then(load)}>{t("delete")}</button>
          </p>
        </div>
      ))}
    </>
  );
}
