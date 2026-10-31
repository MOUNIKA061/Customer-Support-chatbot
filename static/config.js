/**
 * Frontend Configuration
 * Allows configuring the API endpoint via environment or host settings.
 * Default is an empty string (""), which automatically uses relative paths
 * like "/chat" and "/health" when served from the same FastAPI backend.
 */
window.APP_CONFIG = {
  // If hosting the frontend on a separate port or domain (e.g. http://127.0.0.1:8000),
  // set API_BASE_URL here. Leave as "" for relative root routing.
  API_BASE_URL: window.ENV_API_URL || ""
};

