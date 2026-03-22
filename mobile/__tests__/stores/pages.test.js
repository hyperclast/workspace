import usePageStore from "../../stores/pages";
import { fetchPage, updatePage, createPage } from "../../lib/api";

jest.mock("../../lib/api", () => ({
  fetchPage: jest.fn(),
  updatePage: jest.fn(),
  createPage: jest.fn(),
}));

const initialState = usePageStore.getState();

beforeEach(() => {
  usePageStore.setState(initialState, true);
  jest.clearAllMocks();
});

describe("fetchPage", () => {
  it("sets currentPage on success", async () => {
    const mockPage = { external_id: "page-1", title: "Test", details: { content: "hello" } };
    fetchPage.mockResolvedValue(mockPage);

    await usePageStore.getState().fetchPage("page-1");

    expect(fetchPage).toHaveBeenCalledWith("page-1");
    expect(usePageStore.getState().currentPage).toEqual(mockPage);
    expect(usePageStore.getState().loading).toBe(false);
    expect(usePageStore.getState().error).toBeNull();
  });

  it("sets error on failure", async () => {
    fetchPage.mockRejectedValue(new Error("Not found"));

    await usePageStore.getState().fetchPage("bad-id");

    expect(usePageStore.getState().currentPage).toBeNull();
    expect(usePageStore.getState().loading).toBe(false);
    expect(usePageStore.getState().error).toBe("Not found");
  });

  it("clears currentPage when fetching a different page fails", async () => {
    const stalePageA = {
      external_id: "page-a",
      title: "Page A",
      details: { content: "A content" },
    };
    usePageStore.setState({ currentPage: stalePageA });

    fetchPage.mockRejectedValue(new Error("Not found"));

    await usePageStore.getState().fetchPage("page-b");

    expect(usePageStore.getState().currentPage).toBeNull();
    expect(usePageStore.getState().error).toBe("Not found");
  });

  it("clears currentPage at start of fetch", async () => {
    const stalePageA = {
      external_id: "page-a",
      title: "Page A",
      details: { content: "A content" },
    };
    usePageStore.setState({ currentPage: stalePageA });

    let resolvePromise;
    fetchPage.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolvePromise = resolve;
        })
    );

    const promise = usePageStore.getState().fetchPage("page-b");

    expect(usePageStore.getState().currentPage).toBeNull();
    expect(usePageStore.getState().loading).toBe(true);

    resolvePromise({ external_id: "page-b", title: "Page B" });
    await promise;

    expect(usePageStore.getState().currentPage).toEqual({ external_id: "page-b", title: "Page B" });
  });

  it("sets loading to true during fetch", async () => {
    let resolvePromise;
    fetchPage.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolvePromise = resolve;
        })
    );

    const promise = usePageStore.getState().fetchPage("page-1");

    expect(usePageStore.getState().loading).toBe(true);
    expect(usePageStore.getState().error).toBeNull();

    resolvePromise({ external_id: "page-1", title: "Test" });
    await promise;

    expect(usePageStore.getState().loading).toBe(false);
  });
});

describe("updatePage", () => {
  it("calls API with correct data and updates currentPage", async () => {
    const updatedPage = { external_id: "page-1", title: "Updated" };
    updatePage.mockResolvedValue(updatedPage);

    const result = await usePageStore.getState().updatePage("page-1", { title: "Updated" });

    expect(updatePage).toHaveBeenCalledWith("page-1", { title: "Updated" });
    expect(usePageStore.getState().currentPage).toEqual(updatedPage);
    expect(result).toEqual(updatedPage);
  });

  it("sets saving during save", async () => {
    let resolvePromise;
    updatePage.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolvePromise = resolve;
        })
    );

    const promise = usePageStore.getState().updatePage("page-1", { title: "New" });

    expect(usePageStore.getState().saving).toBe(true);

    resolvePromise({ external_id: "page-1", title: "New" });
    await promise;

    expect(usePageStore.getState().saving).toBe(false);
  });

  it("sets error and re-throws on failure", async () => {
    updatePage.mockRejectedValue(new Error("Save failed"));

    await expect(usePageStore.getState().updatePage("page-1", { title: "New" })).rejects.toThrow(
      "Save failed"
    );

    expect(usePageStore.getState().saving).toBe(false);
    expect(usePageStore.getState().error).toBe("Save failed");
  });
});

describe("createPage", () => {
  it("calls API and returns created page", async () => {
    const newPage = { external_id: "new-1", title: "New Page" };
    createPage.mockResolvedValue(newPage);

    const result = await usePageStore.getState().createPage("proj-1", "New Page");

    expect(createPage).toHaveBeenCalledWith("proj-1", "New Page");
    expect(result).toEqual(newPage);
    expect(usePageStore.getState().saving).toBe(false);
  });

  it("sets error and re-throws on failure", async () => {
    createPage.mockRejectedValue(new Error("Create failed"));

    await expect(usePageStore.getState().createPage("proj-1", "Test")).rejects.toThrow(
      "Create failed"
    );

    expect(usePageStore.getState().saving).toBe(false);
    expect(usePageStore.getState().error).toBe("Create failed");
  });
});

describe("clearPage", () => {
  it("clears currentPage and error", () => {
    usePageStore.setState({ currentPage: { title: "Old" }, error: "stale error" });

    usePageStore.getState().clearPage();

    expect(usePageStore.getState().currentPage).toBeNull();
    expect(usePageStore.getState().error).toBeNull();
  });
});
