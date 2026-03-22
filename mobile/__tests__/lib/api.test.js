import {
  apiFetch,
  syncDeviceMetadata,
  loginRequest,
  fetchPage,
  createPage,
  updatePage,
  deletePage,
  fetchMentions,
  fetchMe,
  fetchStorage,
  fetchDevices,
  revokeDevice,
  TOKEN_KEY,
} from "../../lib/api";
import * as Device from "expo-device";
import * as Storage from "../../lib/storage";

const mockClearAuth = jest.fn().mockResolvedValue();

jest.mock("../../stores/auth", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      token: "test-token",
      clearAuth: mockClearAuth,
    }),
  },
}));

jest.mock("../../lib/storage");

const mockFetch = jest.fn();
global.fetch = mockFetch;

beforeEach(() => {
  jest.clearAllMocks();
  mockClearAuth.mockResolvedValue();
});

describe("apiFetch", () => {
  it("sends Authorization header when token exists", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ data: "test" }),
    });

    await apiFetch("/test");

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/test"),
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer test-token",
        }),
      })
    );
  });

  it("sends X-Hyperclast-Client header", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    });

    await apiFetch("/test");

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({
          "X-Hyperclast-Client": expect.stringContaining("client=mobile"),
        }),
      })
    );
  });

  it("returns null for 204 responses", async () => {
    mockFetch.mockResolvedValue({ ok: true, status: 204 });

    const result = await apiFetch("/test");

    expect(result).toBeNull();
  });

  it("calls clearAuth and throws on 401", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 401 });

    await expect(apiFetch("/test")).rejects.toThrow("Unauthorized");
    expect(mockClearAuth).toHaveBeenCalled();
  });

  it("throws with server error message on non-ok response", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: "Internal Server Error" }),
    });

    await expect(apiFetch("/test")).rejects.toThrow("Internal Server Error");
  });

  it("attaches status property to errors for non-ok responses", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ error: "Not found" }),
    });

    try {
      await apiFetch("/test");
      expect("should not reach here").toBe(false);
    } catch (e) {
      expect(e.message).toBe("Not found");
      expect(e.status).toBe(404);
    }
  });

  it("throws 'Request timed out' when timeout fires", async () => {
    jest.useFakeTimers();
    // Mock fetch that respects AbortSignal
    mockFetch.mockImplementation((_url, options) => {
      return new Promise((_resolve, reject) => {
        if (options?.signal) {
          options.signal.addEventListener("abort", () => {
            const err = new Error("The operation was aborted");
            err.name = "AbortError";
            reject(err);
          });
        }
      });
    });

    const promise = apiFetch("/test", { timeoutMs: 100 });

    jest.advanceTimersByTime(100);

    await expect(promise).rejects.toThrow("Request timed out");

    jest.useRealTimers();
  });

  it("does not timeout when timeoutMs is 0", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ data: "ok" }),
    });

    const result = await apiFetch("/test", { timeoutMs: 0 });

    expect(result).toEqual({ data: "ok" });
  });

  it("aborts fetch when caller-provided signal is aborted", async () => {
    const callerController = new AbortController();

    mockFetch.mockImplementation((_url, options) => {
      return new Promise((_resolve, reject) => {
        if (options?.signal) {
          options.signal.addEventListener("abort", () => {
            const err = new Error("The operation was aborted");
            err.name = "AbortError";
            reject(err);
          });
        }
      });
    });

    const promise = apiFetch("/test", { signal: callerController.signal, timeoutMs: 0 });

    callerController.abort();

    // Should be the original AbortError, not wrapped as timeout
    try {
      await promise;
      expect("should not reach here").toBe(false);
    } catch (e) {
      expect(e.name).toBe("AbortError");
      expect(e.code).not.toBe("ETIMEDOUT");
    }
  });

  it("immediately aborts when caller signal is already aborted", async () => {
    const callerController = new AbortController();
    callerController.abort();

    mockFetch.mockImplementation((_url, options) => {
      return new Promise((_resolve, reject) => {
        if (options?.signal?.aborted) {
          const err = new Error("The operation was aborted");
          err.name = "AbortError";
          reject(err);
        }
      });
    });

    await expect(
      apiFetch("/test", { signal: callerController.signal, timeoutMs: 0 })
    ).rejects.toThrow("The operation was aborted");
  });

  it("cleans up caller signal listener after fetch completes", async () => {
    const callerController = new AbortController();
    const removeSpy = jest.spyOn(callerController.signal, "removeEventListener");

    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ data: "ok" }),
    });

    await apiFetch("/test", { signal: callerController.signal, timeoutMs: 0 });

    expect(removeSpy).toHaveBeenCalledWith("abort", expect.any(Function));
    removeSpy.mockRestore();
  });

  it("does not forward timeoutMs to fetch", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    });

    await apiFetch("/test", { timeoutMs: 5000 });

    const [, fetchOptions] = mockFetch.mock.calls[0];
    expect(fetchOptions.timeoutMs).toBeUndefined();
  });
});

describe("syncDeviceMetadata", () => {
  it("sends device details in the PATCH body", async () => {
    Storage.getOrCreateClientId.mockResolvedValue("test-client-id");
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    });

    await syncDeviceMetadata();

    const [, options] = mockFetch.mock.calls[0];
    const body = JSON.parse(options.body);
    expect(body.details).toEqual({
      os_version: expect.any(String),
      model: Device.modelName,
      manufacturer: Device.manufacturer,
      is_device: Device.isDevice,
      brand: Device.brand,
      sdk_version: null,
    });
  });

  it("uses expo-device modelName for device name", async () => {
    Storage.getOrCreateClientId.mockResolvedValue("test-client-id");
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    });

    await syncDeviceMetadata();

    const [, options] = mockFetch.mock.calls[0];
    const body = JSON.parse(options.body);
    expect(body.name).toBe("TestPhone 15");
  });

  it("sends PATCH to the device endpoint with client_id", async () => {
    Storage.getOrCreateClientId.mockResolvedValue("my-device-uuid");
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    });

    await syncDeviceMetadata();

    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain("/users/me/devices/my-device-uuid/");
  });
});

describe("loginRequest timeout", () => {
  it("throws 'Request timed out' when auth endpoint hangs", async () => {
    jest.useFakeTimers();
    Storage.getOrCreateClientId.mockResolvedValue("test-client-id");

    // First fetch (authenticate) hangs indefinitely
    mockFetch.mockImplementation((_url, options) => {
      return new Promise((_resolve, reject) => {
        if (options?.signal) {
          options.signal.addEventListener("abort", () => {
            const err = new Error("The operation was aborted");
            err.name = "AbortError";
            reject(err);
          });
        }
      });
    });

    const promise = loginRequest("user@example.com", "password");

    jest.advanceTimersByTime(15000);

    await expect(promise).rejects.toThrow("Request timed out");

    jest.useRealTimers();
  });

  it("throws 'Request timed out' when device registration hangs", async () => {
    jest.useFakeTimers();
    Storage.getOrCreateClientId.mockResolvedValue("test-client-id");

    let callCount = 0;
    mockFetch.mockImplementation((_url, options) => {
      callCount++;
      if (callCount === 1) {
        // First fetch (authenticate) succeeds with session token
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve({
              meta: { session_token: "session-tok" },
            }),
        });
      }
      // Second fetch (registerDeviceAndGetToken) hangs
      return new Promise((_resolve, reject) => {
        if (options?.signal) {
          options.signal.addEventListener("abort", () => {
            const err = new Error("The operation was aborted");
            err.name = "AbortError";
            reject(err);
          });
        }
      });
    });

    const promise = loginRequest("user@example.com", "password");

    // Attach the rejection handler before advancing timers so the rejection
    // is caught immediately when the timeout fires.
    const assertion = expect(promise).rejects.toThrow("Request timed out");

    // Let the first (resolved) fetch settle, then fire the 15s timeout
    await jest.advanceTimersByTimeAsync(15000);

    await assertion;

    jest.useRealTimers();
  });

  it("sets ETIMEDOUT error code on timeout", async () => {
    jest.useFakeTimers();
    Storage.getOrCreateClientId.mockResolvedValue("test-client-id");

    mockFetch.mockImplementation((_url, options) => {
      return new Promise((_resolve, reject) => {
        if (options?.signal) {
          options.signal.addEventListener("abort", () => {
            const err = new Error("The operation was aborted");
            err.name = "AbortError";
            reject(err);
          });
        }
      });
    });

    const promise = loginRequest("user@example.com", "password");

    jest.advanceTimersByTime(15000);

    try {
      await promise;
      expect("should not reach here").toBe(false);
    } catch (e) {
      expect(e.message).toBe("Request timed out");
      expect(e.code).toBe("ETIMEDOUT");
      expect(e.cause).toBeInstanceOf(Error);
      expect(e.cause.name).toBe("AbortError");
    }

    jest.useRealTimers();
  });

  it("passes through network errors without wrapping as timeout", async () => {
    Storage.getOrCreateClientId.mockResolvedValue("test-client-id");

    mockFetch.mockRejectedValue(new TypeError("Network request failed"));

    await expect(loginRequest("user@example.com", "password")).rejects.toThrow(
      "Network request failed"
    );
    // Verify it's the original TypeError, not wrapped as a timeout
    try {
      await loginRequest("user@example.com", "password");
    } catch (e) {
      expect(e).toBeInstanceOf(TypeError);
      expect(e.code).not.toBe("ETIMEDOUT");
    }
  });
});

describe("loginRequest error handling", () => {
  it("throws user-friendly error when server returns 5xx HTML", async () => {
    Storage.getOrCreateClientId.mockResolvedValue("test-client-id");

    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.reject(new SyntaxError("Unexpected token")),
    });

    await expect(loginRequest("user@example.com", "password")).rejects.toThrow(
      "Server error, please try again"
    );
  });

  it("extracts allauth error message on invalid credentials (400)", async () => {
    Storage.getOrCreateClientId.mockResolvedValue("test-client-id");

    // Allauth 400 response (after APIErrorNormalizerMiddleware)
    mockFetch.mockResolvedValue({
      ok: false,
      status: 400,
      json: () =>
        Promise.resolve({
          error: "error",
          message: "An error occurred.",
          detail: null,
          status: 400,
          errors: [
            {
              message: "The email address and/or password you specified are not correct.",
              code: "email_password_mismatch",
              param: "password",
            },
          ],
        }),
    });

    await expect(loginRequest("user@example.com", "wrong")).rejects.toThrow(
      "The email address and/or password you specified are not correct."
    );
  });

  it("detects pending email verification (401) and shows verification message", async () => {
    Storage.getOrCreateClientId.mockResolvedValue("test-client-id");

    // Allauth 401 response (after APIErrorNormalizerMiddleware)
    mockFetch.mockResolvedValue({
      ok: false,
      status: 401,
      json: () =>
        Promise.resolve({
          error: "error",
          message: "An error occurred.",
          detail: null,
          status: 401,
          data: {
            flows: [{ id: "verify_email", is_pending: true }, { id: "login" }],
          },
          meta: { is_authenticated: false },
        }),
    });

    await expect(loginRequest("user@example.com", "password")).rejects.toThrow(
      "Please verify your email address before signing in."
    );
  });

  it("uses fallback error when no session token and no errors array", async () => {
    Storage.getOrCreateClientId.mockResolvedValue("test-client-id");

    // Allauth 409 (already authenticated) — no errors, no session token
    mockFetch.mockResolvedValue({
      ok: false,
      status: 409,
      json: () =>
        Promise.resolve({
          error: "error",
          message: "An error occurred.",
          detail: null,
          status: 409,
        }),
    });

    await expect(loginRequest("user@example.com", "password")).rejects.toThrow("Login failed");
  });

  it("throws when device registration returns 5xx HTML", async () => {
    Storage.getOrCreateClientId.mockResolvedValue("test-client-id");

    let callCount = 0;
    mockFetch.mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        // Auth succeeds
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ meta: { session_token: "session-tok" } }),
        });
      }
      // Device registration returns 5xx HTML
      return Promise.resolve({
        ok: false,
        status: 500,
        json: () => Promise.reject(new SyntaxError("Unexpected token")),
      });
    });

    await expect(loginRequest("user@example.com", "password")).rejects.toThrow(
      "Server error, please try again"
    );
  });

  it("throws 'Device registration failed' on 422 validation error", async () => {
    Storage.getOrCreateClientId.mockResolvedValue("test-client-id");

    let callCount = 0;
    mockFetch.mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        // Auth succeeds
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ meta: { session_token: "session-tok" } }),
        });
      }
      // 422 with normalized error — no access_token field
      return Promise.resolve({
        ok: false,
        status: 422,
        json: () =>
          Promise.resolve({
            error: "error",
            message: "An error occurred.",
            detail: [{ type: "missing", loc: ["client_id"], msg: "Field required" }],
          }),
      });
    });

    await expect(loginRequest("user@example.com", "password")).rejects.toThrow(
      "Device registration failed"
    );
  });
});

describe("loginRequest success", () => {
  it("passes AbortSignal to fetch during auth and device registration", async () => {
    Storage.getOrCreateClientId.mockResolvedValue("test-client-id");
    Storage.setItemAsync.mockResolvedValue();

    let callCount = 0;
    mockFetch.mockImplementation((_url, options) => {
      callCount++;
      // Both calls should receive an AbortSignal
      expect(options.signal).toBeInstanceOf(AbortSignal);

      if (callCount === 1) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve({
              meta: { session_token: "session-tok" },
            }),
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ access_token: "device-tok" }),
      });
    });

    await loginRequest("user@example.com", "password");

    expect(callCount).toBe(2);
  });

  it("stores access token via Storage.setItemAsync on success", async () => {
    Storage.getOrCreateClientId.mockResolvedValue("test-client-id");
    Storage.setItemAsync.mockResolvedValue();

    let callCount = 0;
    mockFetch.mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ meta: { session_token: "session-tok" } }),
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ access_token: "my-device-token" }),
      });
    });

    const token = await loginRequest("user@example.com", "password");

    expect(token).toBe("my-device-token");
    expect(Storage.setItemAsync).toHaveBeenCalledWith("access_token", "my-device-token");
  });
});

describe("fetchPage", () => {
  it("calls GET /pages/{id}/", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ external_id: "page-123", title: "Test Page" }),
    });

    const result = await fetchPage("page-123");

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/pages/page-123/"),
      expect.objectContaining({ headers: expect.any(Object) })
    );
    expect(result).toEqual({ external_id: "page-123", title: "Test Page" });
  });
});

describe("createPage", () => {
  it("calls POST /pages/ with project_id and title", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 201,
      json: () => Promise.resolve({ external_id: "new-page", title: "My Page" }),
    });

    const result = await createPage("proj-1", "My Page");

    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain("/pages/");
    expect(options.method).toBe("POST");
    const body = JSON.parse(options.body);
    expect(body).toEqual({ project_id: "proj-1", title: "My Page" });
    expect(result).toEqual({ external_id: "new-page", title: "My Page" });
  });

  it("defaults title to 'Untitled' when not provided", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 201,
      json: () => Promise.resolve({ external_id: "new-page", title: "Untitled" }),
    });

    await createPage("proj-1", "");

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.title).toBe("Untitled");
  });
});

describe("updatePage", () => {
  it("calls PUT /pages/{id}/ with data and mode: 'overwrite'", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ external_id: "page-1", title: "Updated" }),
    });

    const result = await updatePage("page-1", {
      title: "Updated",
      details: { content: "new content" },
    });

    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain("/pages/page-1/");
    expect(options.method).toBe("PUT");
    const body = JSON.parse(options.body);
    expect(body).toEqual({
      title: "Updated",
      details: { content: "new content" },
      mode: "overwrite",
    });
    expect(result).toEqual({ external_id: "page-1", title: "Updated" });
  });
});

describe("deletePage", () => {
  it("calls DELETE /pages/{id}/ and returns null", async () => {
    mockFetch.mockResolvedValue({ ok: true, status: 204 });

    const result = await deletePage("page-1");

    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain("/pages/page-1/");
    expect(options.method).toBe("DELETE");
    expect(result).toBeNull();
  });
});

describe("fetchMentions", () => {
  it("calls GET /mentions/ and returns JSON", async () => {
    const mentionsData = { mentions: [{ page_title: "Test" }], total: 1, has_more: false };
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mentionsData),
    });

    const result = await fetchMentions();

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/mentions/"),
      expect.any(Object)
    );
    expect(result).toEqual(mentionsData);
  });
});

describe("fetchMe", () => {
  it("calls GET /users/me/ and returns JSON", async () => {
    const userData = { external_id: "u-1", email: "me@example.com", username: "me" };
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(userData),
    });

    const result = await fetchMe();

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/users/me/"),
      expect.any(Object)
    );
    expect(result).toEqual(userData);
  });
});

describe("fetchStorage", () => {
  it("calls GET /users/storage/ and returns JSON", async () => {
    const storageData = { total_bytes: 1048576, file_count: 3 };
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(storageData),
    });

    const result = await fetchStorage();

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/users/storage/"),
      expect.any(Object)
    );
    expect(result).toEqual(storageData);
  });
});

describe("fetchDevices", () => {
  it("calls GET /users/me/devices/ and returns JSON", async () => {
    const devicesData = [
      { client_id: "dev-1", name: "iPhone", is_current: true },
      { client_id: "dev-2", name: "iPad", is_current: false },
    ];
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(devicesData),
    });

    const result = await fetchDevices();

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/users/me/devices/"),
      expect.any(Object)
    );
    expect(result).toEqual(devicesData);
  });
});

describe("revokeDevice", () => {
  it("calls DELETE /users/me/devices/{clientId}/ and returns null", async () => {
    mockFetch.mockResolvedValue({ ok: true, status: 204 });

    const result = await revokeDevice("dev-2");

    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain("/users/me/devices/dev-2/");
    expect(options.method).toBe("DELETE");
    expect(result).toBeNull();
  });
});
