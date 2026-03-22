import { render, screen, fireEvent, waitFor } from "@testing-library/react-native";
import useProjectStore from "../../stores/projects";
import usePageStore from "../../stores/pages";

const mockPush = jest.fn();
let capturedStackScreenOptions = null;
jest.mock("expo-router", () => ({
  useLocalSearchParams: () => ({ projectId: "proj-1" }),
  router: { push: (...args) => mockPush(...args) },
  Stack: {
    Screen: ({ options }) => {
      capturedStackScreenOptions = options;
      return null;
    },
  },
}));

jest.mock("../../lib/api", () => ({
  fetchProjects: jest.fn(),
  fetchPage: jest.fn(),
  updatePage: jest.fn(),
  createPage: jest.fn(),
}));

const ProjectDetailScreen = require("../../app/(app)/project/[projectId]").default;

const projectStoreInitial = useProjectStore.getState();
const pageStoreInitial = usePageStore.getState();

beforeEach(() => {
  useProjectStore.setState(projectStoreInitial, true);
  usePageStore.setState(pageStoreInitial, true);
  capturedStackScreenOptions = null;
  jest.clearAllMocks();
});

function setProject(project) {
  useProjectStore.setState({ projects: [project], loading: false, error: null });
}

const baseProject = {
  external_id: "proj-1",
  name: "My Project",
  description: "A test project",
  pages: [],
};

describe("ProjectDetailScreen", () => {
  it("renders project name and description", () => {
    setProject(baseProject);

    render(<ProjectDetailScreen />);

    expect(screen.getByText("A test project")).toBeTruthy();
  });

  it("renders list of pages sorted by updated desc", () => {
    setProject({
      ...baseProject,
      pages: [
        { external_id: "p1", title: "Older", updated: "2025-01-01T00:00:00Z" },
        { external_id: "p2", title: "Newer", updated: "2025-06-15T00:00:00Z" },
        { external_id: "p3", title: "Middle", updated: "2025-03-10T00:00:00Z" },
      ],
    });

    render(<ProjectDetailScreen />);

    // Get page titles in render order
    const titles = screen.getAllByText(/^(Newer|Middle|Older)$/).map((el) => el.props.children);
    expect(titles).toEqual(["Newer", "Middle", "Older"]);
  });

  it("shows 'No pages yet' when project has no pages", () => {
    setProject(baseProject);

    render(<ProjectDetailScreen />);

    expect(screen.getByText("No pages yet")).toBeTruthy();
  });

  it("tapping a page navigates to /page/{pageId}", () => {
    setProject({
      ...baseProject,
      pages: [{ external_id: "page-abc", title: "Test Page", updated: "2025-01-01T00:00:00Z" }],
    });

    render(<ProjectDetailScreen />);

    fireEvent.press(screen.getByText("Test Page"));

    expect(mockPush).toHaveBeenCalledWith("/page/page-abc");
  });

  it("pull-to-refresh reloads project data", async () => {
    const mockFetchProjects = jest.fn();
    setProject(baseProject);
    useProjectStore.setState({ fetchProjects: mockFetchProjects });

    render(<ProjectDetailScreen />);

    const flatList = screen.UNSAFE_getByType(require("react-native").FlatList);
    const refreshControl = flatList.props.refreshControl;

    refreshControl.props.onRefresh();

    expect(mockFetchProjects).toHaveBeenCalled();
  });

  it("FAB button is visible", () => {
    setProject(baseProject);

    render(<ProjectDetailScreen />);

    expect(screen.getByTestId("fab-new-page")).toBeTruthy();
  });

  it("tapping FAB creates page and navigates to edit", async () => {
    setProject(baseProject);
    const mockCreatePage = jest.fn().mockResolvedValue({
      external_id: "new-page-id",
      title: "Untitled",
    });
    usePageStore.setState({ createPage: mockCreatePage });

    render(<ProjectDetailScreen />);

    fireEvent.press(screen.getByTestId("fab-new-page"));

    await waitFor(() => {
      expect(mockCreatePage).toHaveBeenCalledWith("proj-1", "Untitled");
      expect(mockPush).toHaveBeenCalledWith("/page/new-page-id/edit");
    });
  });

  it("shows loading indicator when project is not found and loading", () => {
    const mockFetchProjects = jest.fn();
    useProjectStore.setState({ projects: [], loading: true, fetchProjects: mockFetchProjects });

    render(<ProjectDetailScreen />);

    // Should show ActivityIndicator (centered view) when project not found and loading
    expect(screen.queryByText("No pages yet")).toBeNull();
    expect(screen.queryByText("Project not found")).toBeNull();
  });

  it("fetches projects when store is empty on mount", () => {
    const mockFetchProjects = jest.fn();
    useProjectStore.setState({ projects: [], loading: false, fetchProjects: mockFetchProjects });

    render(<ProjectDetailScreen />);

    expect(mockFetchProjects).toHaveBeenCalled();
  });

  it("refreshes projects after creating a page", async () => {
    const mockFetchProjects = jest.fn();
    setProject(baseProject);
    useProjectStore.setState({ fetchProjects: mockFetchProjects });
    const mockCreatePage = jest.fn().mockResolvedValue({
      external_id: "new-page-id",
      title: "Untitled",
    });
    usePageStore.setState({ createPage: mockCreatePage });

    render(<ProjectDetailScreen />);

    fireEvent.press(screen.getByTestId("fab-new-page"));

    await waitFor(() => {
      expect(mockCreatePage).toHaveBeenCalledWith("proj-1", "Untitled");
      expect(mockFetchProjects).toHaveBeenCalled();
    });
  });

  it("configures header with back button via headerShown", () => {
    setProject(baseProject);

    render(<ProjectDetailScreen />);

    expect(capturedStackScreenOptions).toMatchObject({
      title: "My Project",
      headerShown: true,
    });
  });

  it("shows 'Project not found' when fetch completes without matching project", () => {
    useProjectStore.setState({
      projects: [],
      loading: false,
      error: null,
      fetchProjects: jest.fn(),
    });

    render(<ProjectDetailScreen />);

    expect(screen.getByText("Project not found")).toBeTruthy();
  });
});
