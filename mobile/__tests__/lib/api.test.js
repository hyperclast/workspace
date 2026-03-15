import { apiFetch, syncDeviceMetadata, TOKEN_KEY } from "../../lib/api";
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
