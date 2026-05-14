// config.js
// Automatically uses localhost in development and the real backend in production.
// Update PROD_API_BASE after you deploy the backend to Render.

const IS_LOCAL = window.location.hostname === "localhost" ||
                 window.location.hostname === "127.0.0.1";

const API_BASE = IS_LOCAL
  ? "http://localhost:8001"
  : "https://YOUR_RENDER_URL.onrender.com"; // ← replace after Render deploy
