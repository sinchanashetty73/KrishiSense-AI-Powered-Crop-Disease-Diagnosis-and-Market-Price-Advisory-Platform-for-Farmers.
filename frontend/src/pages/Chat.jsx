import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

// Voice uses the browser's Web Speech API (free, no server). Works best in Chrome / Edge on Android and desktop.
// Kannada/Hindi speech recognition and read-aloud depend on the voices installed on the device.
const VOICE_LANG = { en: "en-IN", hi: "hi-IN", kn: "kn-IN" };
const SR = typeof window !== "undefined" ? window.SpeechRecognition || window.webkitSpeechRecognition : null;

export function speak(text, lang) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = VOICE_LANG[lang] || "en-IN";
  window.speechSynthesis.speak(u);
}

export default function Chat({ t, lang }) {
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [auto, setAuto] = useState(false);
  const [sugg, setSugg] = useState([]);
  const [err, setErr] = useState("");
  const end = useRef(null);
  const rec = useRef(null);

  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);
  useEffect(() => { api.chat("help", lang).then((r) => { setSugg(r.suggestions); setMsgs([{ from: "bot", text: r.reply }]); }).catch(() => {}); }, [lang]);
  useEffect(() => () => { rec.current?.stop(); window.speechSynthesis?.cancel(); }, []);

  const send = async (message) => {
    const m = (message ?? text).trim();
    if (!m || busy) return;
    setText(""); setErr(""); setBusy(true);
    setMsgs((x) => [...x, { from: "me", text: m }]);
    try {
      const r = await api.chat(m, lang);
      setMsgs((x) => [...x, { from: "bot", text: r.reply }]);
      setSugg(r.suggestions);
      if (auto) speak(r.reply, lang);
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };

  const listen = () => {
    if (!SR) { setErr(t("voiceUnsupported")); return; }
    if (listening) { rec.current?.stop(); return; }
    const r = new SR();
    r.lang = VOICE_LANG[lang] || "en-IN";
    r.interimResults = false;
    r.onresult = (e) => send(e.results[0][0].transcript);
    r.onerror = () => setListening(false);
    r.onend = () => setListening(false);
    rec.current = r;
    setListening(true);
    r.start();
  };

  return (
    <div className="card">
      <h2>💬 {t("chatTitle")}</h2>
      <div style={{ minHeight: 160 }}>
        {msgs.map((m, i) => (
          <div key={i} className={`bubble ${m.from}`}>
            {m.text}
            {m.from === "bot" && <div><button className="small secondary" style={{ marginTop: 6 }} onClick={() => speak(m.text, lang)}>🔊 {t("readAloud")}</button></div>}
          </div>
        ))}
        <div ref={end} />
      </div>
      <div className="chips">{sugg.map((s) => <button key={s} className="chip" onClick={() => send(s)}>{s}</button>)}</div>
      {err && <div className="error">{err}</div>}
      <div className="row" style={{ alignItems: "center" }}>
        <input style={{ flex: "3 1 200px" }} placeholder={listening ? t("listening") : t("typeMessage")} value={text}
          onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} />
        <button onClick={() => send()} disabled={busy || !text.trim()}>{t("send")}</button>
        <button className={listening ? "" : "secondary"} onClick={listen} aria-label={t("mic")}>🎤 {listening ? t("listening") : t("mic")}</button>
      </div>
      <label style={{ fontWeight: 400 }}><input type="checkbox" style={{ width: "auto" }} checked={auto} onChange={(e) => setAuto(e.target.checked)} /> {t("autoSpeak")}</label>
    </div>
  );
}
