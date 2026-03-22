import { render, screen, fireEvent, waitFor, act } from "@testing-library/react-native";
import { Alert } from "react-native";
import useAuthStore from "../../stores/auth";

const mockReplace = jest.fn();
jest.mock("expo-router", () => ({
  router: { replace: (...args) => mockReplace(...args) },
}));

jest.mock("expo-constants", () => ({
  expoConfig: { version: "1.2.3" },
}));

jest.mock("../../lib/api", () => ({
  fetchMe: jest.fn(),
  fetchStorage: jest.fn(),
  fetchDevices: jest.fn(),
  revokeDevice: jest.fn(),
  loginRequest: jest.fn(),
  signupRequest: jest.fn(),
  logoutRequest: jest.fn(),
  syncDeviceMetadata: jest.fn(),
  TOKEN_KEY: "access_token",
}));

const { fetchMe, fetchStorage, fetchDevices, revokeDevice } = require("../../lib/api");

const SettingsScreen = require("../../app/(app)/(tabs)/settings").default;

const authInitial = useAuthStore.getState();

beforeEach(() => {
  useAuthStore.setState(authInitial, true);
  jest.clearAllMocks();
});

function mockAllApis({ user, storage, devices } = {}) {
  fetchMe.mockResolvedValue(
    user || { external_id: "u1", email: "alice@example.com", username: "alice" }
  );
  fetchStorage.mockResolvedValue(storage || { total_bytes: 2097152, file_count: 5 });
  fetchDevices.mockResolvedValue(
    devices || [
      {
        client_id: "dev-1",
        name: "iPhone 15",
        os: "ios",
        last_active: "2025-06-15T10:00:00Z",
        is_current: true,
      },
      {
        client_id: "dev-2",
        name: "iPad Air",
        os: "ios",
        last_active: "2025-06-14T08:00:00Z",
        is_current: false,
      },
    ]
  );
}

describe("SettingsScreen", () => {
  it("shows user email and username", async () => {
    mockAllApis();

    render(<SettingsScreen />);

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeTruthy();
    });
    expect(screen.getByText("alice")).toBeTruthy();
  });

  it("shows storage usage", async () => {
    mockAllApis();

    render(<SettingsScreen />);

    await waitFor(() => {
      expect(screen.getByText(/5.*files.*2 MB.*used/)).toBeTruthy();
    });
  });

  it("shows device list with current device indicator", async () => {
    mockAllApis();

    render(<SettingsScreen />);

    await waitFor(() => {
      expect(screen.getByText("iPhone 15")).toBeTruthy();
    });
    expect(screen.getByText("iPad Air")).toBeTruthy();
    expect(screen.getByText("Current")).toBeTruthy();
  });

  it("tapping revoke on non-current device calls revokeDevice", async () => {
    mockAllApis();
    revokeDevice.mockResolvedValue(null);
    jest.spyOn(Alert, "alert");

    render(<SettingsScreen />);

    await waitFor(() => {
      expect(screen.getByText("iPad Air")).toBeTruthy();
    });

    // The remove button should only appear for non-current devices
    const removeButtons = screen.getAllByText("Remove");
    expect(removeButtons).toHaveLength(1);
    fireEvent.press(removeButtons[0]);

    // Should show confirmation dialog
    expect(Alert.alert).toHaveBeenCalledWith(
      "Remove device?",
      expect.stringContaining("iPad Air"),
      expect.arrayContaining([
        expect.objectContaining({ text: "Cancel", style: "cancel" }),
        expect.objectContaining({ text: "Remove", style: "destructive" }),
      ])
    );

    // Simulate pressing "Remove" in the alert
    const alertCall = Alert.alert.mock.calls[0];
    const revokeAction = alertCall[2].find((b) => b.text === "Remove");
    await act(() => revokeAction.onPress());

    expect(revokeDevice).toHaveBeenCalledWith("dev-2");
  });

  it("cannot revoke current device", async () => {
    mockAllApis({
      devices: [
        {
          client_id: "dev-1",
          name: "iPhone 15",
          os: "ios",
          last_active: "2025-06-15T10:00:00Z",
          is_current: true,
        },
      ],
    });

    render(<SettingsScreen />);

    await waitFor(() => {
      expect(screen.getByText("iPhone 15")).toBeTruthy();
    });

    // No Remove button should appear for the current device
    expect(screen.queryByText("Remove")).toBeNull();
  });

  it("shows user info even when fetchStorage fails", async () => {
    fetchMe.mockResolvedValue({ external_id: "u1", email: "alice@example.com", username: "alice" });
    fetchStorage.mockRejectedValue(new Error("Storage unavailable"));
    fetchDevices.mockResolvedValue([]);

    render(<SettingsScreen />);

    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeTruthy();
    });
    expect(screen.getByText("alice")).toBeTruthy();
    // Storage section should not render
    expect(screen.queryByText("Storage")).toBeNull();
  });

  it("shows storage even when fetchDevices fails", async () => {
    fetchMe.mockResolvedValue({ external_id: "u1", email: "alice@example.com", username: "alice" });
    fetchStorage.mockResolvedValue({ total_bytes: 2097152, file_count: 5 });
    fetchDevices.mockRejectedValue(new Error("Devices unavailable"));

    render(<SettingsScreen />);

    await waitFor(() => {
      expect(screen.getByText(/5.*files.*2 MB.*used/)).toBeTruthy();
    });
    // Devices section should not render
    expect(screen.queryByText("Devices")).toBeNull();
  });

  it("shows storage and devices even when fetchMe fails", async () => {
    fetchMe.mockRejectedValue(new Error("User unavailable"));
    fetchStorage.mockResolvedValue({ total_bytes: 2097152, file_count: 5 });
    fetchDevices.mockResolvedValue([
      {
        client_id: "dev-1",
        name: "iPhone 15",
        os: "ios",
        last_active: "2025-06-15T10:00:00Z",
        is_current: true,
      },
    ]);

    render(<SettingsScreen />);

    await waitFor(() => {
      expect(screen.getByText(/5.*files.*2 MB.*used/)).toBeTruthy();
    });
    expect(screen.getByText("iPhone 15")).toBeTruthy();
    // Account section should not render
    expect(screen.queryByText("Account")).toBeNull();
  });

  it("logout flow works", async () => {
    mockAllApis();
    const mockLogout = jest.fn().mockResolvedValue(undefined);
    useAuthStore.setState({ logout: mockLogout });

    render(<SettingsScreen />);

    await waitFor(() => {
      expect(screen.getByText("Sign out")).toBeTruthy();
    });

    fireEvent.press(screen.getByText("Sign out"));

    await waitFor(() => {
      expect(mockLogout).toHaveBeenCalled();
      expect(mockReplace).toHaveBeenCalledWith("/login");
    });
  });
});
