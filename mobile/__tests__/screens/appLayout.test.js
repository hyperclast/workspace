import { render, screen } from "@testing-library/react-native";
import useAuthStore from "../../stores/auth";

const mockReplace = jest.fn();
let capturedStackProps = null;
const mockStack = jest.fn((props) => {
  capturedStackProps = props;
  return null;
});
mockStack.Screen = jest.fn(() => null);

jest.mock("expo-router", () => ({
  Stack: mockStack,
  router: { replace: (...args) => mockReplace(...args) },
}));

jest.mock("../../lib/api", () => ({
  fetchProjects: jest.fn(),
}));

const AppLayout = require("../../app/(app)/_layout").default;

const initialState = useAuthStore.getState();

beforeEach(() => {
  useAuthStore.setState(initialState, true);
  capturedStackProps = null;
  jest.clearAllMocks();
});

describe("AppLayout", () => {
  it("renders a Stack navigator with headerShown false by default", () => {
    useAuthStore.setState({ hydrated: true, token: "test-token", loadToken: jest.fn() });

    render(<AppLayout />);

    expect(mockStack).toHaveBeenCalled();
    expect(capturedStackProps.screenOptions).toEqual({ headerShown: false });
  });

  it("shows splash screen while loading token", () => {
    useAuthStore.setState({ hydrated: false, token: null, loadToken: jest.fn() });

    render(<AppLayout />);

    expect(mockStack).not.toHaveBeenCalled();
  });

  it("redirects to login when hydrated without token", () => {
    useAuthStore.setState({ hydrated: true, token: null, loadToken: jest.fn() });

    render(<AppLayout />);

    expect(mockReplace).toHaveBeenCalledWith("/login");
  });
});
