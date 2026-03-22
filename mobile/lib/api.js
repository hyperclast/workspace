import { Platform } from "react-native";
import Constants from "expo-constants";
import * as Device from "expo-device";
import * as Storage from "./storage";

const API_URL = process.env.EXPO_PUBLIC_API_URL || "http://localhost:9800/api/v1";
const API_ORIGIN = API_URL.replace(/\/api\/v1\/?$/, "") || "http://localhost:9800";
const AUTH_BASE = `${API_ORIGIN}/api/app/v1`;
const TOKEN_KEY = "access_token";
const DEFAULT_TIMEOUT_MS = 15000;

// Lazy require breaks the circular import: stores/auth.js imports from api.js,
// and apiFetch needs to read token + clear auth from the store. The lazy require
// is only resolved on first apiFetch call, by which point both modules are fully
// initialized. This is the only coupling point between api.js and the store.
let _authStore = null;
function getAuthStore() {
  if (!_authStore) {
    _authStore = require("../stores/auth").default;
  }
  return _authStore;
}

function buildClientHeader() {
  const os = Platform.OS;
  const version = Constants.expoConfig?.version || "0.0.0";
  const arch = Platform.constants?.utsname?.machine || "unknown";
  return `client=mobile; version=${version}; os=${os}; arch=${arch}`;
}

function getDeviceName() {
  if (Device.modelName) return Device.modelName;
  if (Device.manufacturer) return `${Device.manufacturer} device`;
  return `${Platform.OS} device`;
}

function buildDeviceDetails() {
  return {
    os_version: String(Platform.Version),
    model: Device.modelName || null,
    manufacturer: Device.manufacturer || null,
    is_device: Device.isDevice,
    brand: Device.brand || null,
    sdk_version: Constants.expoConfig?.sdkVersion || null,
  };
}

async function apiFetch(path, options = {}) {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...fetchOptions } = options;
  const token = getAuthStore().getState().token;

  const controller = new AbortController();
  let didTimeout = false;
  let timeoutId = null;
  let onCallerAbort = null;

  // Link caller-provided signal so either side can cancel.
  if (fetchOptions.signal) {
    const callerSignal = fetchOptions.signal;
    if (callerSignal.aborted) {
      controller.abort(callerSignal.reason);
    } else {
      onCallerAbort = () => controller.abort(callerSignal.reason);
      callerSignal.addEventListener("abort", onCallerAbort);
    }
  }

  if (timeoutMs > 0) {
    timeoutId = setTimeout(() => {
      didTimeout = true;
      controller.abort();
    }, timeoutMs);
  }

  try {
    const res = await fetch(`${API_URL}${path}`, {
      ...fetchOptions,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        "X-Hyperclast-Client": buildClientHeader(),
        ...fetchOptions.headers,
      },
    });
    if (res.status === 401) {
      await getAuthStore().getState().clearAuth();
      throw new Error("Unauthorized");
    }
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      const message = body?.message || body?.error || `HTTP ${res.status}`;
      const err = new Error(message);
      err.status = res.status;
      throw err;
    }
    if (res.status === 204) return null;
    return res.json();
  } catch (e) {
    if (e instanceof Error && e.name === "AbortError") {
      if (didTimeout) {
        const err = new Error("Request timed out", { cause: e });
        err.code = "ETIMEDOUT";
        throw err;
      }
      throw e;
    }
    throw e;
  } finally {
    if (timeoutId !== null) clearTimeout(timeoutId);
    if (onCallerAbort && fetchOptions.signal) {
      fetchOptions.signal.removeEventListener("abort", onCallerAbort);
    }
  }
}

function hasPendingEmailVerification(data) {
  return data?.data?.flows?.some((f) => f.id === "verify_email" && f.is_pending);
}

// Minimal fetch wrapper with timeout support. Used by authenticate() and
// registerDeviceAndGetToken() which run BEFORE auth is established and need
// raw Response access (allauth returns structured errors in 4xx bodies).
// apiFetch() can't be used here because it requires a token and auto-throws
// on !res.ok, which would prevent parsing allauth's error responses.
async function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController();
  let didTimeout = false;
  const timeoutId = setTimeout(() => {
    didTimeout = true;
    controller.abort();
  }, DEFAULT_TIMEOUT_MS);

  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (e) {
    if (e instanceof Error && e.name === "AbortError" && didTimeout) {
      const err = new Error("Request timed out", { cause: e });
      err.code = "ETIMEDOUT";
      throw err;
    }
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

async function registerDeviceAndGetToken(sessionToken) {
  const clientId = await Storage.getOrCreateClientId();

  const res = await fetchWithTimeout(`${API_URL}/users/me/devices/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Token": sessionToken,
      "X-Hyperclast-Client": buildClientHeader(),
    },
    body: JSON.stringify({
      client_id: clientId,
      name: getDeviceName(),
      os: Platform.OS,
      app_version: Constants.expoConfig?.version || "0.0.0",
      details: buildDeviceDetails(),
    }),
  });

  if (res.status >= 500) {
    throw new Error("Server error, please try again");
  }
  const data = await res.json().catch(() => null);
  if (!data?.access_token) {
    throw new Error("Device registration failed");
  }
  await Storage.setItemAsync(TOKEN_KEY, data.access_token);
  return data.access_token;
}

async function authenticate(url, email, password, fallbackError) {
  const res = await fetchWithTimeout(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Client-Type": "app",
    },
    body: JSON.stringify({ email, password }),
  });

  if (res.status >= 500) {
    throw new Error("Server error, please try again");
  }
  const data = await res.json().catch(() => null);
  if (!data) {
    throw new Error("Server error, please try again");
  }

  if (hasPendingEmailVerification(data)) {
    throw new Error(
      "Please verify your email address before signing in. Check your inbox for a verification link."
    );
  }
  const sessionToken = data.meta?.session_token;
  if (!sessionToken) {
    const errors = data.errors || [];
    const msg = errors.map((e) => e.message).join(". ") || fallbackError;
    throw new Error(msg);
  }
  return registerDeviceAndGetToken(sessionToken);
}

async function loginRequest(email, password) {
  return authenticate(`${AUTH_BASE}/auth/login`, email, password, "Login failed");
}

async function signupRequest(email, password) {
  return authenticate(`${AUTH_BASE}/auth/signup`, email, password, "Signup failed");
}

async function logoutRequest() {
  const clientId = await Storage.getOrCreateClientId();
  await apiFetch(`/users/me/devices/${clientId}/`, { method: "DELETE" });
}

async function syncDeviceMetadata() {
  const clientId = await Storage.getOrCreateClientId();
  await apiFetch(`/users/me/devices/${clientId}/`, {
    method: "PATCH",
    body: JSON.stringify({
      name: getDeviceName(),
      os: Platform.OS,
      app_version: Constants.expoConfig?.version || "0.0.0",
      details: buildDeviceDetails(),
    }),
  });
}

async function fetchProjects() {
  return apiFetch("/projects/?details=full");
}

export {
  API_URL,
  TOKEN_KEY,
  apiFetch,
  loginRequest,
  signupRequest,
  logoutRequest,
  fetchProjects,
  syncDeviceMetadata,
};
