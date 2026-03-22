import useProjectStore from "../../stores/projects";
import { fetchProjects } from "../../lib/api";

jest.mock("../../lib/api", () => ({
  fetchProjects: jest.fn(),
}));

const initialState = useProjectStore.getState();

beforeEach(() => {
  useProjectStore.setState(initialState, true);
  jest.clearAllMocks();
});

describe("fetchProjects", () => {
  it("sets projects and clears loading on success", async () => {
    const mockProjects = [
      { external_id: "p1", name: "Project 1", pages: [] },
      { external_id: "p2", name: "Project 2", pages: [] },
    ];
    fetchProjects.mockResolvedValue(mockProjects);

    await useProjectStore.getState().fetchProjects();

    expect(useProjectStore.getState().projects).toEqual(mockProjects);
    expect(useProjectStore.getState().loading).toBe(false);
    expect(useProjectStore.getState().error).toBeNull();
  });

  it("sets error on failure", async () => {
    fetchProjects.mockRejectedValue(new Error("Network error"));

    await useProjectStore.getState().fetchProjects();

    expect(useProjectStore.getState().projects).toEqual([]);
    expect(useProjectStore.getState().loading).toBe(false);
    expect(useProjectStore.getState().error).toBe("Network error");
  });

  it("sets loading to true during fetch", async () => {
    let resolvePromise;
    fetchProjects.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolvePromise = resolve;
        })
    );

    const promise = useProjectStore.getState().fetchProjects();

    expect(useProjectStore.getState().loading).toBe(true);
    expect(useProjectStore.getState().error).toBeNull();

    resolvePromise([]);
    await promise;

    expect(useProjectStore.getState().loading).toBe(false);
  });

  it("defaults to empty array when API returns non-array", async () => {
    fetchProjects.mockResolvedValue(null);

    await useProjectStore.getState().fetchProjects();

    expect(useProjectStore.getState().projects).toEqual([]);
  });
});
