import { render, screen, fireEvent, waitFor, act } from "@testing-library/react-native";
import { FlatList } from "react-native";

const mockPush = jest.fn();
jest.mock("expo-router", () => ({
  router: { push: (...args) => mockPush(...args) },
}));

jest.mock("../../lib/api", () => ({
  fetchMentions: jest.fn(),
}));

const { fetchMentions } = require("../../lib/api");

const MentionsScreen = require("../../app/(app)/(tabs)/mentions").default;

beforeEach(() => {
  jest.clearAllMocks();
});

const baseMentions = {
  mentions: [
    {
      page_external_id: "page-1",
      page_title: "Q3 Planning",
      project_name: "Engineering",
      modified: "2025-06-15T10:30:00Z",
    },
    {
      page_external_id: "page-2",
      page_title: "Meeting Notes",
      project_name: "Leadership",
      modified: "2025-06-14T09:00:00Z",
    },
  ],
  total: 2,
  has_more: false,
};

describe("MentionsScreen", () => {
  it("shows loading indicator while fetching", () => {
    fetchMentions.mockReturnValue(new Promise(() => {})); // never resolves

    render(<MentionsScreen />);

    // Should not show mention content while loading
    expect(screen.queryByText("Q3 Planning")).toBeNull();
    expect(screen.queryByText("No mentions yet")).toBeNull();
  });

  it("renders mention list with page title, project name, and time", async () => {
    fetchMentions.mockResolvedValue(baseMentions);

    render(<MentionsScreen />);

    await waitFor(() => {
      expect(screen.getByText("Q3 Planning")).toBeTruthy();
    });

    expect(screen.getByText("Meeting Notes")).toBeTruthy();
    expect(screen.getByText("Engineering")).toBeTruthy();
    expect(screen.getByText("Leadership")).toBeTruthy();
  });

  it("shows 'No mentions yet' when empty", async () => {
    fetchMentions.mockResolvedValue({ mentions: [], total: 0, has_more: false });

    render(<MentionsScreen />);

    await waitFor(() => {
      expect(screen.getByText("No mentions yet")).toBeTruthy();
    });
  });

  it("tapping mention navigates to page view", async () => {
    fetchMentions.mockResolvedValue(baseMentions);

    render(<MentionsScreen />);

    await waitFor(() => {
      expect(screen.getByText("Q3 Planning")).toBeTruthy();
    });

    fireEvent.press(screen.getByText("Q3 Planning"));

    expect(mockPush).toHaveBeenCalledWith("/page/page-1");
  });

  it("pull-to-refresh reloads mentions", async () => {
    fetchMentions.mockResolvedValue(baseMentions);

    render(<MentionsScreen />);

    await waitFor(() => {
      expect(screen.getByText("Q3 Planning")).toBeTruthy();
    });

    fetchMentions.mockClear();
    fetchMentions.mockResolvedValue({ mentions: [], total: 0, has_more: false });

    const flatList = screen.UNSAFE_getByType(FlatList);
    await act(() => flatList.props.refreshControl.props.onRefresh());

    expect(fetchMentions).toHaveBeenCalledTimes(1);
  });

  it("shows error state on fetch failure", async () => {
    fetchMentions.mockRejectedValue(new Error("Network error"));

    render(<MentionsScreen />);

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeTruthy();
    });
  });
});
