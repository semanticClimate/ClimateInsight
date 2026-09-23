/* api.js — all backend calls in one place */

// Resolve the API base dynamically from the current origin so local dev,
// Cloudflare tunnels, and production all work without editing this file.
// scripts/inject-tunnel.py may override CLIMATEINSIGHT_CONFIG.apiBase at
// deploy time (e.g. "https://provisions-tire-tap-parking.trycloudflare.com/api").
function resolveApiBase() {
  const configured = window.CLIMATEINSIGHT_CONFIG?.apiBase?.trim();
  const base = (configured || window.location.origin).replace(/\/+$/, "");
  return base.endsWith("/api") ? base : `${base}/api`;
}

const API_BASE = resolveApiBase();
const apiLogs = [];

function logRequest(method, url, status) {
  apiLogs.push({
    timestamp: new Date().toLocaleTimeString(),
    method,
    url,
    status
  });
  if (apiLogs.length > 50) apiLogs.shift();

  // Trigger update event
  document.dispatchEvent(new CustomEvent("api-log-updated"));
}

const Api = {
  getLogs() {
    return apiLogs;
  },

  async health() {
    try {
      const res = await fetch(`${API_BASE}/health`);
      logRequest("GET", "/health", res.status);
      return res.ok;
    } catch (err) {
      logRequest("GET", "/health", "FAILED");
      throw err;
    }
  },

  async chat(question, sessionId, language = "en") {
    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, session_id: sessionId, language }),
      });
      logRequest("POST", "/chat", res.status);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Request failed");
      return data; // { answer, citations, session_id, language }
    } catch (err) {
      if (err.message !== "Request failed") {
        logRequest("POST", "/chat", "FAILED");
      }
      throw err;
    }
  },

  async clearSession(sessionId) {
    if (!sessionId) return;
    try {
      const res = await fetch(`${API_BASE}/session/${sessionId}`, { method: "DELETE" });
      logRequest("DELETE", `/session/${sessionId}`, res.status);
    } catch (err) {
      logRequest("DELETE", `/session/${sessionId}`, "FAILED");
    }
  },
};