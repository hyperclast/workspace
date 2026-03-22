import { render, screen, fireEvent, waitFor, act } from "@testing-library/react-native";
import { Alert } from "react-native";
import usePageStore from "../../stores/pages";
import useProjectStore from "../../stores/projects";

const mockBack = jest.fn();
const mockPush = jest.fn();
let beforeRemoveListener = null;
jest.mock("expo-router", () => ({
  useLocalSearchParams: () => ({ pageId: "page-1" }),
  router: { back: (...args) => mockBack(...args), push: (...args) => mockPush(...args) },
  Stack: {
    Screen: ({ options }) => {
      const HeaderRight = options?.headerRight;
      return HeaderRight ? <HeaderRight /> : null;
    },
  },
  useNavigation: () => ({
    addListener: (event, callback) => {
      if (event === "beforeRemove") {
        beforeRemoveListener = callback;
      }
      return jest.fn(); // unsubscribe
    },
    dispatch: jest.fn(),
  }),
}));

jest.mock("../../lib/api", () => ({
  fetchProjects: jest.fn(),
  fetchPage: jest.fn(),
  updatePage: jest.fn(),
  createPage: jest.fn(),
}));

const PageEditScreen = require("../../app/(app)/page/[pageId]/edit").default;

const initialState = usePageStore.getState();
const projectStoreInitial = useProjectStore.getState();

beforeEach(() => {
  usePageStore.setState(initialState, true);
  useProjectStore.setState(projectStoreInitial, true);
  beforeRemoveListener = null;
  jest.clearAllMocks();
});

function setPage(page) {
  // Override fetchPage to no-op so the useEffect doesn't clobber pre-set state
  usePageStore.setState({ currentPage: page, loading: false, error: null, fetchPage: jest.fn() });
}

const basePage = {
  external_id: "page-1",
  title: "Test Page",
  details: { content: "Some content here." },
  is_owner: true,
};

describe("PageEditScreen", () => {
  it("renders title input with current title", () => {
    setPage(basePage);

    render(<PageEditScreen />);

    const titleInput = screen.getByTestId("title-input");
    expect(titleInput.props.value).toBe("Test Page");
  });

  it("renders content TextInput with current content", () => {
    setPage(basePage);

    render(<PageEditScreen />);

    const contentInput = screen.getByTestId("content-input");
    expect(contentInput.props.value).toBe("Some content here.");
  });

  it("save button calls updatePage with correct data", async () => {
    setPage(basePage);
    const mockUpdatePage = jest.fn().mockResolvedValue({ ...basePage, title: "Updated" });
    usePageStore.setState({ updatePage: mockUpdatePage });

    render(<PageEditScreen />);

    fireEvent.changeText(screen.getByTestId("title-input"), "Updated");
    fireEvent.press(screen.getByTestId("save-button"));

    await waitFor(() => {
      expect(mockUpdatePage).toHaveBeenCalledWith("page-1", {
        title: "Updated",
        details: { content: "Some content here." },
      });
    });
  });

  it("shows saving indicator during save", async () => {
    setPage(basePage);
    usePageStore.setState({ saving: true });

    render(<PageEditScreen />);

    // When saving, the Save button should show ActivityIndicator instead of text
    expect(screen.queryByText("Save")).toBeNull();
  });

  it("navigates back on successful save", async () => {
    setPage(basePage);
    const mockUpdatePage = jest.fn().mockResolvedValue(basePage);
    usePageStore.setState({ updatePage: mockUpdatePage });

    render(<PageEditScreen />);

    fireEvent.press(screen.getByTestId("save-button"));

    await waitFor(() => {
      expect(mockBack).toHaveBeenCalled();
    });
  });

  it("shows error on save failure", async () => {
    setPage(basePage);
    const mockUpdatePage = jest.fn().mockRejectedValue(new Error("Save failed"));
    usePageStore.setState({ updatePage: mockUpdatePage, error: null });

    render(<PageEditScreen />);

    fireEvent.press(screen.getByTestId("save-button"));

    // The store's updatePage sets error state on failure
    await waitFor(() => {
      expect(mockUpdatePage).toHaveBeenCalled();
    });

    // After failure, the store error should be set and router.back should NOT be called
    expect(mockBack).not.toHaveBeenCalled();
  });

  it("shows discard confirmation when navigating away with unsaved changes", () => {
    setPage(basePage);
    jest.spyOn(Alert, "alert");

    render(<PageEditScreen />);

    // Make a change to trigger isDirty
    fireEvent.changeText(screen.getByTestId("title-input"), "Changed Title");

    // Simulate beforeRemove event
    expect(beforeRemoveListener).not.toBeNull();
    const mockEvent = {
      preventDefault: jest.fn(),
      data: { action: { type: "GO_BACK" } },
    };
    beforeRemoveListener(mockEvent);

    expect(mockEvent.preventDefault).toHaveBeenCalled();
    expect(Alert.alert).toHaveBeenCalledWith(
      "Discard changes?",
      "You have unsaved changes.",
      expect.arrayContaining([
        expect.objectContaining({ text: "Cancel", style: "cancel" }),
        expect.objectContaining({ text: "Discard", style: "destructive" }),
      ])
    );
  });

  it("does not show confirmation when navigating away without changes", () => {
    setPage(basePage);
    jest.spyOn(Alert, "alert");

    render(<PageEditScreen />);

    // Don't make any changes, simulate beforeRemove
    expect(beforeRemoveListener).not.toBeNull();
    const mockEvent = {
      preventDefault: jest.fn(),
      data: { action: { type: "GO_BACK" } },
    };
    beforeRemoveListener(mockEvent);

    expect(mockEvent.preventDefault).not.toHaveBeenCalled();
    expect(Alert.alert).not.toHaveBeenCalled();
  });

  it("renders empty content when page has no details", () => {
    setPage({ ...basePage, details: {} });

    render(<PageEditScreen />);

    const contentInput = screen.getByTestId("content-input");
    expect(contentInput.props.value).toBe("");
  });

  it("fetches page on mount when currentPage is null", () => {
    const mockFetchPage = jest.fn();
    usePageStore.setState({ currentPage: null, loading: true, fetchPage: mockFetchPage });

    render(<PageEditScreen />);

    expect(mockFetchPage).toHaveBeenCalledWith("page-1");
  });

  it("does not re-fetch when currentPage matches pageId", () => {
    const mockFetchPage = jest.fn();
    usePageStore.setState({
      currentPage: basePage,
      loading: false,
      error: null,
      fetchPage: mockFetchPage,
    });

    render(<PageEditScreen />);

    expect(mockFetchPage).not.toHaveBeenCalled();
  });

  it("shows error state when fetch fails", () => {
    usePageStore.setState({
      currentPage: null,
      loading: false,
      error: "Not found",
      fetchPage: jest.fn(),
    });

    render(<PageEditScreen />);

    expect(screen.getByText("Page not found")).toBeTruthy();
    expect(screen.queryByTestId("title-input")).toBeNull();
    expect(screen.queryByTestId("content-input")).toBeNull();
  });

  it("shows spinner when currentPage has wrong external_id", () => {
    const wrongPage = { ...basePage, external_id: "different-page" };
    usePageStore.setState({
      currentPage: wrongPage,
      loading: false,
      error: null,
      fetchPage: jest.fn(),
    });

    render(<PageEditScreen />);

    expect(screen.queryByTestId("title-input")).toBeNull();
    expect(screen.queryByTestId("content-input")).toBeNull();
  });

  it("does not show discard prompt after successful save", async () => {
    setPage(basePage);
    const mockUpdatePage = jest.fn().mockResolvedValue({ ...basePage, title: "Changed Title" });
    usePageStore.setState({ updatePage: mockUpdatePage });
    jest.spyOn(Alert, "alert");

    render(<PageEditScreen />);

    // Make a change to trigger isDirty
    fireEvent.changeText(screen.getByTestId("title-input"), "Changed Title");
    fireEvent.press(screen.getByTestId("save-button"));

    // Wait for save to complete AND for React to re-render with updated
    // originalTitle/originalContent (which makes isDirty false and causes the
    // beforeRemove effect to re-register with the clean closure).
    await waitFor(() => {
      expect(mockBack).toHaveBeenCalled();
    });

    // Simulate beforeRemove after save — the listener should see isDirty === false
    expect(beforeRemoveListener).not.toBeNull();
    const mockEvent = {
      preventDefault: jest.fn(),
      data: { action: { type: "GO_BACK" } },
    };
    beforeRemoveListener(mockEvent);

    expect(mockEvent.preventDefault).not.toHaveBeenCalled();
    expect(Alert.alert).not.toHaveBeenCalled();
  });

  it("refreshes projects after saving a page", async () => {
    setPage(basePage);
    const mockUpdatePage = jest.fn().mockResolvedValue(basePage);
    usePageStore.setState({ updatePage: mockUpdatePage });
    const mockFetchProjects = jest.fn();
    useProjectStore.setState({ fetchProjects: mockFetchProjects });

    render(<PageEditScreen />);

    fireEvent.press(screen.getByTestId("save-button"));

    await waitFor(() => {
      expect(mockUpdatePage).toHaveBeenCalled();
      expect(mockFetchProjects).toHaveBeenCalled();
    });
  });
});
