/**
 * config.js — Fetches app metadata from /api/config (which reads config.toml server-side).
 * Exposes a global APP_CONFIG promise AND a convenience APP_CONFIG_READY promise.
 * Other scripts should await window.APP_CONFIG_READY before reading window.APP_CONFIG.
 */

window.APP_CONFIG = null;

window.APP_CONFIG_READY = (async () => {
  try {
    // API_BASE is injected by api.js (loaded just before this script)
    const base = (typeof API_BASE !== "undefined" ? API_BASE : "").replace(/\/api$/, "");
    const res  = await fetch(`${base}/api/config`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    window.APP_CONFIG = await res.json();
  } catch (err) {
    console.warn("[config.js] Could not load config.toml from backend:", err);
    // Minimal fallback so the UI doesn't break if the backend is down
    window.APP_CONFIG = { app: { version: "—" } };
  }
  return window.APP_CONFIG;
})();
