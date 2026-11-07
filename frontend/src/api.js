// All calls go to /api (proxied to FastAPI by Vite in dev and by nginx/ALB in production).
const BASE = "/api";

export const getToken = () => localStorage.getItem("ks_token");
export const setToken = (t) => (t ? localStorage.setItem("ks_token", t) : localStorage.removeItem("ks_token"));

async function request(path, { method = "GET", body, form } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body) headers["Content-Type"] = "application/json";
  const res = await fetch(BASE + path, { method, headers, body: form || (body ? JSON.stringify(body) : undefined) });
  if (res.status === 401) {
    setToken(null);
    window.dispatchEvent(new Event("ks-logout"));
  }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {}
    throw new Error(msg);
  }
  return res.json();
}

export const api = {
  requestOtp: (phone) => request("/auth/request-otp", { method: "POST", body: { phone } }),
  verifyOtp: (phone, code, name, language) => request("/auth/verify-otp", { method: "POST", body: { phone, code, name, language } }),
  me: () => request("/me"),
  updateMe: (data) => request("/me", { method: "PATCH", body: data }),
  crops: () => request("/crops"),
  markets: () => request("/markets"),
  scan: (file, cropId, coords) => {
    const form = new FormData();
    form.append("file", file);
    if (cropId) form.append("crop_id", cropId);
    if (coords) { form.append("lat", coords.latitude); form.append("lon", coords.longitude); }
    return request("/scans", { method: "POST", form });
  },
  scans: () => request("/scans"),
  feedback: (id, correct) => request(`/scans/${id}/feedback`, { method: "POST", body: { correct } }),
  prices: (cropId, marketId, days = 60) => request(`/prices?crop_id=${cropId}&market_id=${marketId}&days=${days}`),
  forecast: (cropId, marketId, horizon = 7) => request(`/prices/forecast?crop_id=${cropId}&market_id=${marketId}&horizon=${horizon}`),
  bestMarket: (cropId) => request(`/prices/best-market?crop_id=${cropId}`),
  profit: (data) => request("/prices/profit", { method: "POST", body: data }),
  alerts: () => request("/alerts"),
  createAlert: (data) => request("/alerts", { method: "POST", body: data }),
  deleteAlert: (id) => request(`/alerts/${id}`, { method: "DELETE" }),
  testAlert: () => request("/alerts/test", { method: "POST" }),
  pushKey: () => request("/push/public-key"),
  pushSubscribe: (sub) => request("/push/subscribe", { method: "POST", body: sub }),
  pushUnsubscribe: (endpoint) => request(`/push/subscribe?endpoint=${encodeURIComponent(endpoint)}`, { method: "DELETE" }),
  outbreaks: (days = 30) => request(`/outbreaks?days=${days}`),
  // advisory, dosage
  spray: () => request("/advisory/spray"),
  diseases: () => request("/diseases"),
  dosage: (data) => request("/dosage", { method: "POST", body: data }),
  // marketplace
  fairPrice: (cropId) => request(`/market/fair-price?crop_id=${cropId}`),
  listings: (cropId) => request(`/market/listings${cropId ? `?crop_id=${cropId}` : ""}`),
  myListings: () => request("/market/my-listings"),
  createListing: (form) => request("/market/listings", { method: "POST", form }),
  updateListing: (id, data) => request(`/market/listings/${id}`, { method: "PATCH", body: data }),
  removeListing: (id) => request(`/market/listings/${id}`, { method: "DELETE" }),
  inquire: (id, message) => request(`/market/listings/${id}/inquire`, { method: "POST", body: { message } }),
  inquiries: () => request("/market/inquiries"),
  // inventory
  inventory: () => request("/inventory"),
  addStock: (data) => request("/inventory", { method: "POST", body: data }),
  deleteStock: (id) => request(`/inventory/${id}`, { method: "DELETE" }),
  // assistant
  chat: (message, language) => request("/chat", { method: "POST", body: { message, language } }),
};
