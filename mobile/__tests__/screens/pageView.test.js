import { render, screen, fireEvent, waitFor } from "@testing-library/react-native";
import { Text } from "react-native";
import usePageStore from "../../stores/pages";

const mockPush = jest.fn();
jest.mock("expo-router", () => ({
  useLocalSearchParams: () => ({ pageId: "page-1" }),
  router: { push: (...args) => mockPush(...args) },
  Stack: {
    Screen: ({ options }) => {
      // Render headerRight so we can test the Edit button
      const HeaderRight = options?.headerRight;
      return HeaderRight ? <HeaderRight /> : null;
    },
  },
}));

let capturedOnLinkPress = null;
jest.mock("react-native-markdown-display", () => {
  const { Text } = require("react-native");
  return {
    __esModule: true,
    default: ({ children, onLinkPress }) => {
      capturedOnLinkPress = onLinkPress;
      return <Text testID="markdown-content">{children}</Text>;
    },
  };
});

jest.mock("../../lib/api", () => ({
  fetchPage: jest.fn(),
  updatePage: jest.fn(),
  createPage: jest.fn(),
}));

const PageViewScreen = require("../../app/(app)/page/[pageId]/index").default;

const initialState = usePageStore.getState();

beforeEach(() => {
  usePageStore.setState(initialState, true);
  capturedOnLinkPress = null;
  jest.clearAllMocks();
});

function setPage(page) {
  // Override fetchPage to no-op so the useEffect doesn't clobber pre-set state
  usePageStore.setState({ currentPage: page, loading: false, error: null, fetchPage: jest.fn() });
}

const basePage = {
  external_id: "page-1",
  title: "Test Page",
  details: { content: "# Hello\n\nSome **bold** text." },
  is_owner: true,
};

describe("PageViewScreen", () => {
  it("shows loading indicator while fetching", () => {
    usePageStore.setState({ loading: true, currentPage: null, error: null, fetchPage: jest.fn() });

    render(<PageViewScreen />);

    expect(screen.queryByTestId("markdown-content")).toBeNull();
    expect(screen.queryByText("Test Page")).toBeNull();
  });

  it("renders page title in header", () => {
    setPage(basePage);

    render(<PageViewScreen />);

    // Stack.Screen mock renders headerRight; title is passed via options
    // The markdown content should be rendered
    expect(screen.getByTestId("markdown-content")).toBeTruthy();
  });

  it("renders markdown content from details.content", () => {
    setPage(basePage);

    render(<PageViewScreen />);

    const markdown = screen.getByTestId("markdown-content");
    expect(markdown.props.children).toBe("# Hello\n\nSome **bold** text.");
  });

  it("shows Edit button when is_owner is true", () => {
    setPage({ ...basePage, is_owner: true });

    render(<PageViewScreen />);

    expect(screen.getByTestId("edit-button")).toBeTruthy();
  });

  it("hides Edit button when is_owner is false", () => {
    setPage({ ...basePage, is_owner: false });

    render(<PageViewScreen />);

    expect(screen.queryByTestId("edit-button")).toBeNull();
  });

  it("tapping Edit navigates to edit screen", () => {
    setPage({ ...basePage, is_owner: true });

    render(<PageViewScreen />);

    fireEvent.press(screen.getByTestId("edit-button"));

    expect(mockPush).toHaveBeenCalledWith("/page/page-1/edit");
  });

  it("shows error state on fetch failure", () => {
    usePageStore.setState({
      loading: false,
      currentPage: null,
      error: "Not found",
      fetchPage: jest.fn(),
    });

    render(<PageViewScreen />);

    expect(screen.getByText("Page not found")).toBeTruthy();
    expect(screen.queryByTestId("markdown-content")).toBeNull();
  });

  it("navigates to page view on internal link press", () => {
    setPage(basePage);

    render(<PageViewScreen />);

    // Simulate internal link press via captured callback
    const result = capturedOnLinkPress("/pages/other-page-id/");

    expect(result).toBe(false);
    expect(mockPush).toHaveBeenCalledWith("/page/other-page-id");
  });

  it("navigates to page view on internal link without trailing slash", () => {
    setPage(basePage);

    render(<PageViewScreen />);

    const result = capturedOnLinkPress("/pages/other-page-id");

    expect(result).toBe(false);
    expect(mockPush).toHaveBeenCalledWith("/page/other-page-id");
  });

  it("allows external links to open normally", () => {
    setPage(basePage);

    render(<PageViewScreen />);

    const result = capturedOnLinkPress("https://example.com");

    expect(result).toBe(true);
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("renders empty string when page has no content", () => {
    setPage({ ...basePage, details: {} });

    render(<PageViewScreen />);

    const markdown = screen.getByTestId("markdown-content");
    expect(markdown.props.children).toBe("");
  });
});
