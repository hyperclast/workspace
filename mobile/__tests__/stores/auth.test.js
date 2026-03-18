import useAuthStore from "../../stores/auth";
import * as Storage from "../../lib/storage";
import {
  TOKEN_KEY,
  loginRequest,
  signupRequest,
  logoutRequest,
  syncDeviceMetadata,
} from "../../lib/api";

jest.mock("../../lib/storage");
jest.mock("../../lib/api", () => ({
  TOKEN_KEY: "access_token",
  loginRequest: jest.fn(),
  signupRequest: jest.fn(),
  logoutRequest: jest.fn(),
  syncDeviceMetadata: jest.fn(),
}));

const initialState = useAuthStore.getState();

beforeEach(() => {
  useAuthStore.setState(initialState, true);
  jest.clearAllMocks();
});

describe("loadToken", () => {
  it("hydrates token from storage", async () => {
    Storage.getItemAsync.mockResolvedValue("stored-token");
    syncDeviceMetadata.mockResolvedValue();

    await useAuthStore.getState().loadToken();

    expect(Storage.getItemAsync).toHaveBeenCalledWith(TOKEN_KEY);
    expect(useAuthStore.getState().token).toBe("stored-token");
    expect(useAuthStore.getState().hydrated).toBe(true);
    expect(syncDeviceMetadata).toHaveBeenCalled();
  });

  it("sets hydrated with null token when storage is empty", async () => {
    Storage.getItemAsync.mockResolvedValue(null);

    await useAuthStore.getState().loadToken();

    expect(useAuthStore.getState().token).toBeNull();
    expect(useAuthStore.getState().hydrated).toBe(true);
    expect(syncDeviceMetadata).not.toHaveBeenCalled();
  });

  it("is idempotent — second call is a no-op", async () => {
    Storage.getItemAsync.mockResolvedValue("token");
    syncDeviceMetadata.mockResolvedValue();

    await useAuthStore.getState().loadToken();
    await useAuthStore.getState().loadToken();

    expect(Storage.getItemAsync).toHaveBeenCalledTimes(1);
  });

  it("handles storage failure gracefully", async () => {
    Storage.getItemAsync.mockRejectedValue(new Error("Keychain denied"));

    await useAuthStore.getState().loadToken();

    expect(useAuthStore.getState().token).toBeNull();
    expect(useAuthStore.getState().hydrated).toBe(true);
  });

  it("clears auth when syncDeviceMetadata returns 404 (device revoked)", async () => {
    Storage.getItemAsync.mockResolvedValue("stored-token");
    Storage.deleteItemAsync.mockResolvedValue();
    const err404 = new Error("Not found");
    err404.status = 404;
    syncDeviceMetadata.mockRejectedValue(err404);

    await useAuthStore.getState().loadToken();

    // syncDeviceMetadata is fire-and-forget; flush the .catch() handler
    await new Promise((r) => setImmediate(r));

    expect(useAuthStore.getState().token).toBeNull();
    expect(Storage.deleteItemAsync).toHaveBeenCalledWith(TOKEN_KEY);
  });

  it("keeps auth when syncDeviceMetadata fails with non-404 error", async () => {
    Storage.getItemAsync.mockResolvedValue("stored-token");
    syncDeviceMetadata.mockRejectedValue(new Error("Network error"));

    await useAuthStore.getState().loadToken();

    // Flush the fire-and-forget .catch() handler
    await new Promise((r) => setImmediate(r));

    expect(useAuthStore.getState().token).toBe("stored-token");
  });
});

describe("login", () => {
  it("sets token from loginRequest return value", async () => {
    loginRequest.mockResolvedValue("new-token");

    await useAuthStore.getState().login("user@example.com", "password");

    expect(loginRequest).toHaveBeenCalledWith("user@example.com", "password");
    expect(useAuthStore.getState().token).toBe("new-token");
  });

  it("does not set token when loginRequest throws", async () => {
    loginRequest.mockRejectedValue(new Error("Invalid credentials"));

    await expect(useAuthStore.getState().login("user@example.com", "wrong")).rejects.toThrow(
      "Invalid credentials"
    );

    expect(useAuthStore.getState().token).toBeNull();
  });
});

describe("signup", () => {
  it("sets token from signupRequest return value", async () => {
    signupRequest.mockResolvedValue("signup-token");

    await useAuthStore.getState().signup("new@example.com", "password");

    expect(signupRequest).toHaveBeenCalledWith("new@example.com", "password");
    expect(useAuthStore.getState().token).toBe("signup-token");
  });
});

describe("logout", () => {
  it("clears token and storage", async () => {
    useAuthStore.setState({ token: "existing-token" });
    logoutRequest.mockResolvedValue();
    Storage.deleteItemAsync.mockResolvedValue();

    await useAuthStore.getState().logout();

    expect(logoutRequest).toHaveBeenCalled();
    expect(Storage.deleteItemAsync).toHaveBeenCalledWith(TOKEN_KEY);
    expect(useAuthStore.getState().token).toBeNull();
  });

  it("clears token even when logoutRequest fails", async () => {
    useAuthStore.setState({ token: "existing-token" });
    logoutRequest.mockRejectedValue(new Error("Network error"));
    Storage.deleteItemAsync.mockResolvedValue();

    // logout() re-throws after finally block runs cleanup
    await expect(useAuthStore.getState().logout()).rejects.toThrow("Network error");

    expect(Storage.deleteItemAsync).toHaveBeenCalledWith(TOKEN_KEY);
    expect(useAuthStore.getState().token).toBeNull();
  });
});

describe("clearAuth", () => {
  it("clears token and storage without server call", async () => {
    useAuthStore.setState({ token: "existing-token" });
    Storage.deleteItemAsync.mockResolvedValue();

    await useAuthStore.getState().clearAuth();

    expect(logoutRequest).not.toHaveBeenCalled();
    expect(Storage.deleteItemAsync).toHaveBeenCalledWith(TOKEN_KEY);
    expect(useAuthStore.getState().token).toBeNull();
  });
});
