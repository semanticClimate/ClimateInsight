/*
 * Runtime deployment settings.
 *
 * Local development serves the frontend on port 3000 and the backend on
 * port 5001, so an explicit backend URL is required. Deployments may replace
 * this file with their own URL (or an empty object for same-origin hosting).
 *
 * window.CLIMATEINSIGHT_CONFIG = { apiBase: "https://api.example.com/api" };
 */
window.CLIMATEINSIGHT_CONFIG = {
  apiBase: "http://localhost:5001/api"
};
