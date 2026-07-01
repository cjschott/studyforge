const DEFAULT_API_CANDIDATES = ["", "http://127.0.0.1:8000"];

const state = {
  available: false,
  authenticated: false,
  baseUrl: "",
  health: null,
  user: null
};

function joinUrl(baseUrl, path) {
  return `${baseUrl}${path}`;
}

export function apiState() {
  return { ...state };
}

export function isBackendAvailable() {
  return state.available;
}

export function isBackendMode() {
  return state.available && state.authenticated;
}

export function setBackendUser(user) {
  state.user = user || null;
  state.authenticated = Boolean(user);
}

export async function detectBackend() {
  const candidates = window.STUDYFORGE_API_BASES || DEFAULT_API_CANDIDATES;
  for (const baseUrl of candidates) {
    try {
      const response = await fetch(joinUrl(baseUrl, "/api/admin/health"), {
        cache: "no-store",
        credentials: "include"
      });
      if (response.ok) {
        state.available = true;
        state.baseUrl = baseUrl;
        state.health = await response.json();
        return apiState();
      }
    } catch (error) {
      console.debug(`StudyForge backend not available at ${baseUrl || "same-origin"}.`, error);
    }
  }
  state.available = false;
  state.authenticated = false;
  state.baseUrl = "";
  state.health = null;
  state.user = null;
  return apiState();
}

export async function apiFetch(path, options = {}) {
  if (!state.available) {
    throw new Error("StudyForge backend is not available.");
  }
  const response = await fetch(joinUrl(state.baseUrl, path), {
    ...options,
    credentials: "include",
    headers: {
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(options.headers || {})
    }
  });
  if (response.status === 401) {
    setBackendUser(null);
  }
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch (error) {
      // Ignore non-JSON error bodies.
    }
    throw new Error(message);
  }
  if (response.status === 204) return null;
  return response.json();
}

export function apiGet(path) {
  return apiFetch(path);
}

export function apiPost(path, payload = {}) {
  return apiFetch(path, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function apiPatch(path, payload = {}) {
  return apiFetch(path, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function apiDelete(path) {
  return apiFetch(path, { method: "DELETE" });
}
