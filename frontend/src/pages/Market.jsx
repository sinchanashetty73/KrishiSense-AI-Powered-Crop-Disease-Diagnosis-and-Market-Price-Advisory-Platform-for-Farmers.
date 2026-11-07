import { useEffect, useState } from "react";
import { api } from "../api.js";

function Listing({ l, t, children }) {
  const pct = l.price_vs_market_pct;
  return (
    <div className="card listing">
      {l.image_url && <img src={l.image_url} alt={l.title} />}
      <h3 style={{ margin: "0 0 4px" }}>{l.title}</h3>
      <div>{l.crop} · {l.quantity_qtl} {t("quintals")} · <b>₹{l.price_per_qtl}</b>/q</div>
      {pct != null && (
        <span className={`badge ${pct > 10 ? "bad" : pct < -10 ? "ok" : "warn"}`}>
          {Math.abs(pct) < 1 ? t("atMarket") : `${Math.abs(pct)}% ${pct > 0 ? t("aboveMarket") : t("belowMarket")}`}
        </span>
      )}
      {l.description && <p>{l.description}</p>}
      <p className="muted">{t("seller")}: {l.seller_name}{l.district ? ` · ${l.district}` : ""} · {new Date(l.created_at + "Z").toLocaleDateString()}</p>
      {children}
    </div>
  );
}

export default function Market({ t, crops, cropName, params }) {
  const [view, setView] = useState(params.prefill ? "sell" : "browse");
  const [filter, setFilter] = useState("");
  const [list, setList] = useState([]);
  const [mine, setMine] = useState([]);
  const [inbox, setInbox] = useState([]);
  const [open, setOpen] = useState(null);
  const [msg, setMsg] = useState("");
  const [info, setInfo] = useState("");
  const [err, setErr] = useState("");
  const [f, setF] = useState({ crop_id: params.prefill?.crop_id ? String(params.prefill.crop_id) : "", title: "", quantity_qtl: params.prefill?.quantity ? String(params.prefill.quantity) : "", price_per_qtl: "", description: "" });
  const [file, setFile] = useState(null);
  const [fair, setFair] = useState(null);

  const load = () => {
    api.listings(filter).then(setList).catch((e) => setErr(e.message));
    api.myListings().then(setMine).catch(() => {});
    api.inquiries().then(setInbox).catch(() => {});
  };
  useEffect(load, [filter]);
  useEffect(() => { if (!f.crop_id && crops.length) setF((x) => ({ ...x, crop_id: String(crops[0].id) })); }, [crops]);
  useEffect(() => { if (f.crop_id) api.fairPrice(f.crop_id).then(setFair).catch(() => setFair(null)); }, [f.crop_id]);

  const sendInquiry = async (id) => {
    setErr(""); setInfo("");
    try { const r = await api.inquire(id, msg); setInfo(r.message || t("sentOk")); setOpen(null); setMsg(""); } catch (e) { setErr(e.message); }
  };
  const publish = async () => {
    setErr(""); setInfo("");
    const form = new FormData();
    Object.entries(f).forEach(([k, v]) => form.append(k, v));
    if (file) form.append("file", file);
    try { await api.createListing(form); setInfo(t("published")); setFile(null); setF({ ...f, title: "", description: "", price_per_qtl: "" }); load(); setView("mine"); }
    catch (e) { setErr(e.message); }
  };
  const act = (p) => p.then(load).catch((e) => setErr(e.message));

  return (
    <>
      <div className="seg">
        {[["browse", "mBrowse"], ["sell", "mSell"], ["mine", "mMine"], ["inbox", "mInbox"]].map(([id, label]) => (
          <button key={id} className={view === id ? "on" : ""} onClick={() => { setView(id); setErr(""); setInfo(""); }}>{t(label)}{id === "inbox" && inbox.length ? ` (${inbox.length})` : ""}</button>
        ))}
      </div>
      {err && <div className="error">{err}</div>}
      {info && <div className="banner">{info}</div>}
      <p className="muted">🔒 {t("privacyNote")}</p>

      {view === "browse" && (
        <>
          <select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="">{t("anyCrop")}</option>
            {crops.map((c) => <option key={c.id} value={c.id}>{cropName(c)}</option>)}
          </select>
          {list.length === 0 && <p className="muted">{t("noListings")}</p>}
          {list.map((l) => (
            <Listing key={l.id} l={l} t={t}>
              {!l.mine && (open === l.id ? (
                <>
                  <textarea rows={3} maxLength={500} placeholder={t("yourMessage")} value={msg} onChange={(e) => setMsg(e.target.value)} />
                  <p><button disabled={msg.trim().length < 3} onClick={() => sendInquiry(l.id)}>{t("send")}</button></p>
                </>
              ) : <button onClick={() => { setOpen(l.id); setMsg(""); }}>{t("contactSeller")}</button>)}
            </Listing>
          ))}
        </>
      )}

      {view === "sell" && (
        <div className="card">
          <label>{t("crop")}</label>
          <select value={f.crop_id} onChange={(e) => setF({ ...f, crop_id: e.target.value })}>{crops.map((c) => <option key={c.id} value={c.id}>{cropName(c)}</option>)}</select>
          <label>{t("listingTitle")}</label><input maxLength={120} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} />
          <div className="row">
            <div><label>{t("qtyQtl")}</label><input inputMode="decimal" value={f.quantity_qtl} onChange={(e) => setF({ ...f, quantity_qtl: e.target.value })} /></div>
            <div><label>{t("askingPrice")}</label><input inputMode="decimal" value={f.price_per_qtl} onChange={(e) => setF({ ...f, price_per_qtl: e.target.value })} /></div>
          </div>
          {fair?.market_price && <p className="muted">{t("fairPrice")}: ₹{Math.round(fair.market_price)} · {t("suggested")}: ₹{Math.round(fair.suggested_min)} – ₹{Math.round(fair.suggested_max)}</p>}
          <label>{t("description")}</label><textarea rows={3} maxLength={1000} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
          <label>{t("photo")}</label><input type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          <p><button disabled={f.title.trim().length < 3 || !+f.quantity_qtl || !+f.price_per_qtl} onClick={publish}>{t("publish")}</button></p>
        </div>
      )}

      {view === "mine" && (
        <>
          {mine.length === 0 && <p className="muted">{t("noListings")}</p>}
          {mine.map((l) => (
            <Listing key={l.id} l={l} t={t}>
              <span className={`badge ${l.status === "sold" ? "warn" : "ok"}`}>{l.status === "sold" ? t("sold") : t("active")}</span>{" "}
              {l.status === "active" && <button className="small" onClick={() => act(api.updateListing(l.id, { status: "sold" }))}>{t("markSold")}</button>}{" "}
              <button className="small secondary" onClick={() => act(api.removeListing(l.id))}>{t("remove")}</button>
            </Listing>
          ))}
        </>
      )}

      {view === "inbox" && (
        <>
          {inbox.length === 0 && <p className="muted">{t("noListings")}</p>}
          {inbox.map((i) => (
            <div className="card" key={i.id}>
              <b>{i.listing_title}</b>
              <p>“{i.message}”</p>
              <p className="muted">{i.buyer_name} · {new Date(i.created_at + "Z").toLocaleString()}</p>
              <a href={`tel:${i.buyer_phone}`}><button>📞 {t("callBuyer")} {i.buyer_phone}</button></a>
            </div>
          ))}
        </>
      )}
    </>
  );
}
