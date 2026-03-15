import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";
import * as Crypto from "expo-crypto";

// expo-secure-store has no web implementation, so fall back to localStorage on web.
// Web is dev-only — localStorage is acceptable here. Not a production target.
const isWeb = Platform.OS === "web";

const CLIENT_ID_KEY = "hyperclast_client_id";

export async function getItemAsync(key) {
  if (isWeb) {
    return localStorage.getItem(key);
  }
  return SecureStore.getItemAsync(key);
}

export async function setItemAsync(key, value) {
  if (isWeb) {
    localStorage.setItem(key, value);
    return;
  }
  return SecureStore.setItemAsync(key, value);
}

export async function deleteItemAsync(key) {
  if (isWeb) {
    localStorage.removeItem(key);
    return;
  }
  return SecureStore.deleteItemAsync(key);
}

/**
 * Get or create a stable client ID for this app installation.
 * Persists across app launches. Resets on reinstall (secure storage is wiped).
 */
export async function getOrCreateClientId() {
  let clientId = await getItemAsync(CLIENT_ID_KEY);
  if (!clientId) {
    clientId = Crypto.randomUUID();
    await setItemAsync(CLIENT_ID_KEY, clientId);
  }
  return clientId;
}
