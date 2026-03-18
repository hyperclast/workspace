import { create } from "zustand";
import * as Storage from "../lib/storage";
import {
  TOKEN_KEY,
  loginRequest,
  signupRequest,
  logoutRequest,
  syncDeviceMetadata,
} from "../lib/api";

const useAuthStore = create((set, get) => ({
  token: null,
  hydrated: false,

  loadToken: async () => {
    if (get().hydrated) return;
    try {
      const token = await Storage.getItemAsync(TOKEN_KEY);
      set({ token, hydrated: true });
      if (token) {
        void syncDeviceMetadata().catch((e) => {
          if (e?.status === 404) {
            get().clearAuth();
          }
        });
      }
    } catch {
      set({ token: null, hydrated: true });
    }
  },

  login: async (email, password) => {
    const token = await loginRequest(email, password);
    set({ token });
  },

  signup: async (email, password) => {
    const token = await signupRequest(email, password);
    set({ token });
  },

  logout: async () => {
    try {
      await logoutRequest();
    } finally {
      await Storage.deleteItemAsync(TOKEN_KEY).catch(() => {});
      set({ token: null });
    }
  },

  clearAuth: async () => {
    await Storage.deleteItemAsync(TOKEN_KEY).catch(() => {});
    set({ token: null });
  },
}));

export default useAuthStore;
