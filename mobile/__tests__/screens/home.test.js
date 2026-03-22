import { render, screen, waitFor } from "@testing-library/react-native";
import useProjectStore from "../../stores/projects";

const mockPush = jest.fn();
jest.mock("expo-router", () => ({
  router: { push: (...args) => mockPush(...args) },
}));

jest.mock("../../lib/api", () => ({
  fetchProjects: jest.fn(),
}));

const ProjectListScreen = require("../../app/(app)/(tabs)/index").default;

const initialState = useProjectStore.getState();

beforeEach(() => {
  useProjectStore.setState(initialState, true);
  jest.clearAllMocks();
});

const multiOrgProjects = [
  {
    external_id: "proj-1",
    name: "Project Alpha",
    description: "First project",
    org: { external_id: "org-1", name: "Acme" },
    pages: [{ external_id: "p1" }, { external_id: "p2" }],
  },
  {
    external_id: "proj-2",
    name: "Project Beta",
    description: null,
    org: null,
    pages: [],
  },
];

const singleOrgProjects = [
  {
    external_id: "proj-1",
    name: "Project Alpha",
    description: "First project",
    org: { external_id: "org-1", name: "Acme" },
    pages: [{ external_id: "p1" }, { external_id: "p2" }],
  },
  {
    external_id: "proj-3",
    name: "Project Gamma",
    description: null,
    org: { external_id: "org-1", name: "Acme" },
    pages: [{ external_id: "p3" }],
  },
];

describe("ProjectListScreen (Home)", () => {
  it("calls fetchProjects from the store on mount", () => {
    const mockFetchProjects = jest.fn();
    useProjectStore.setState({ fetchProjects: mockFetchProjects, loading: true });

    render(<ProjectListScreen />);

    expect(mockFetchProjects).toHaveBeenCalledTimes(1);
  });

  it("renders projects from the store with page counts", () => {
    useProjectStore.setState({
      projects: multiOrgProjects,
      loading: false,
      error: null,
      fetchProjects: jest.fn(),
    });

    render(<ProjectListScreen />);

    expect(screen.getByText("Project Alpha")).toBeTruthy();
    expect(screen.getByText("Project Beta")).toBeTruthy();
    expect(screen.getByText("First project")).toBeTruthy();
    expect(screen.getByText("2 pages")).toBeTruthy();
    expect(screen.getByText("0 pages")).toBeTruthy();
  });

  it("shows section headers when projects span multiple orgs", () => {
    useProjectStore.setState({
      projects: multiOrgProjects,
      loading: false,
      error: null,
      fetchProjects: jest.fn(),
    });

    render(<ProjectListScreen />);

    expect(screen.getByText("Acme")).toBeTruthy();
    expect(screen.getByText("Personal")).toBeTruthy();
  });

  it("omits section headers when all projects share one org", () => {
    useProjectStore.setState({
      projects: singleOrgProjects,
      loading: false,
      error: null,
      fetchProjects: jest.fn(),
    });

    render(<ProjectListScreen />);

    expect(screen.getByText("Project Alpha")).toBeTruthy();
    expect(screen.getByText("Project Gamma")).toBeTruthy();
    expect(screen.queryByText("Acme")).toBeNull();
  });
});
