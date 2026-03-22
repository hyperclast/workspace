import { render } from "@testing-library/react-native";

const mockTabsScreen = jest.fn(({ children }) => children || null);
mockTabsScreen.Screen = jest.fn(({ options }) => {
  // Render the icon if provided, so we can assert on icon presence
  const icon = options?.tabBarIcon?.({ color: "#000", size: 24 });
  return icon || null;
});

jest.mock("expo-router", () => ({
  Tabs: mockTabsScreen,
}));

jest.mock("@expo/vector-icons/Ionicons", () => {
  const { Text } = require("react-native");
  return function MockIonicons({ name, size, color }) {
    return <Text testID={`icon-${name}`}>{name}</Text>;
  };
});

const TabsLayout = require("../../app/(app)/(tabs)/_layout").default;

beforeEach(() => {
  jest.clearAllMocks();
});

describe("TabsLayout", () => {
  it("renders without crashing", () => {
    render(<TabsLayout />);
  });

  it("configures three tabs with icons", () => {
    render(<TabsLayout />);

    expect(mockTabsScreen.Screen).toHaveBeenCalledTimes(3);

    const calls = mockTabsScreen.Screen.mock.calls;
    const tabConfigs = calls.map((c) => ({
      name: c[0].name,
      icon: c[0].options?.tabBarIcon ? true : false,
    }));

    expect(tabConfigs).toEqual([
      { name: "index", icon: true },
      { name: "mentions", icon: true },
      { name: "settings", icon: true },
    ]);
  });
});
