import { describe, it, expect } from "vitest";
import { buildTree, getFolderBreadcrumbs } from "../lib/utils/buildTree.js";

// ---------------------------------------------------------------------------
// buildTree()
// ---------------------------------------------------------------------------

describe("buildTree", () => {
  it("returns empty root arrays when given no folders and no pages", () => {
    const { rootFolders, rootPages, folderMap } = buildTree([], []);
    expect(rootFolders).toEqual([]);
    expect(rootPages).toEqual([]);
    expect(folderMap.size).toBe(0);
  });

  it("puts all pages into rootPages when there are no folders", () => {
    const pages = [
      { external_id: "p1", folder_id: null, title: "Zebra" },
      { external_id: "p2", folder_id: null, title: "Apple" },
    ];
    const { rootFolders, rootPages } = buildTree([], pages);

    expect(rootFolders).toEqual([]);
    expect(rootPages).toHaveLength(2);
    // Sorted A-Z by title
    expect(rootPages[0].title).toBe("Apple");
    expect(rootPages[1].title).toBe("Zebra");
  });

  it("nests pages inside a single root folder", () => {
    const folders = [{ external_id: "f1", parent_id: null, name: "Design" }];
    const pages = [
      { external_id: "p1", folder_id: "f1", title: "Wireframes" },
      { external_id: "p2", folder_id: "f1", title: "Colors" },
    ];
    const { rootFolders, rootPages } = buildTree(folders, pages);

    expect(rootPages).toHaveLength(0);
    expect(rootFolders).toHaveLength(1);
    expect(rootFolders[0].name).toBe("Design");
    expect(rootFolders[0].pages).toHaveLength(2);
    // Pages sorted A-Z by title
    expect(rootFolders[0].pages[0].title).toBe("Colors");
    expect(rootFolders[0].pages[1].title).toBe("Wireframes");
  });

  it("builds nested folder hierarchy (parent → child)", () => {
    const folders = [
      { external_id: "f1", parent_id: null, name: "Design" },
      { external_id: "f2", parent_id: "f1", name: "Wireframes" },
    ];
    const pages = [{ external_id: "p1", folder_id: "f2", title: "Homepage" }];
    const { rootFolders } = buildTree(folders, pages);

    expect(rootFolders).toHaveLength(1);
    expect(rootFolders[0].name).toBe("Design");
    expect(rootFolders[0].subfolders).toHaveLength(1);
    expect(rootFolders[0].subfolders[0].name).toBe("Wireframes");
    expect(rootFolders[0].subfolders[0].pages).toHaveLength(1);
    expect(rootFolders[0].subfolders[0].pages[0].title).toBe("Homepage");
  });

  it("falls orphaned pages back to root when folder_id is unknown", () => {
    const folders = [{ external_id: "f1", parent_id: null, name: "Design" }];
    const pages = [
      { external_id: "p1", folder_id: "f1", title: "In folder" },
      { external_id: "p2", folder_id: "deleted_folder", title: "Orphan" },
    ];
    const { rootFolders, rootPages } = buildTree(folders, pages);

    expect(rootPages).toHaveLength(1);
    expect(rootPages[0].title).toBe("Orphan");
    expect(rootFolders[0].pages).toHaveLength(1);
    expect(rootFolders[0].pages[0].title).toBe("In folder");
  });

  it("sorts root folders A-Z by name", () => {
    const folders = [
      { external_id: "f1", parent_id: null, name: "Zebra" },
      { external_id: "f2", parent_id: null, name: "Apple" },
      { external_id: "f3", parent_id: null, name: "Mango" },
    ];
    const { rootFolders } = buildTree(folders, []);

    expect(rootFolders.map((f) => f.name)).toEqual(["Apple", "Mango", "Zebra"]);
  });

  it("sorts subfolders A-Z by name", () => {
    const folders = [
      { external_id: "f1", parent_id: null, name: "Design" },
      { external_id: "f2", parent_id: "f1", name: "Zulu" },
      { external_id: "f3", parent_id: "f1", name: "Alpha" },
    ];
    const { rootFolders } = buildTree(folders, []);

    expect(rootFolders[0].subfolders.map((f) => f.name)).toEqual(["Alpha", "Zulu"]);
  });

  it("handles mixed root pages and root folders independently", () => {
    const folders = [{ external_id: "f1", parent_id: null, name: "Engineering" }];
    const pages = [
      { external_id: "p1", folder_id: null, title: "Standalone" },
      { external_id: "p2", folder_id: "f1", title: "In folder" },
    ];
    const { rootFolders, rootPages } = buildTree(folders, pages);

    expect(rootFolders).toHaveLength(1);
    expect(rootFolders[0].name).toBe("Engineering");
    expect(rootFolders[0].pages).toHaveLength(1);
    expect(rootPages).toHaveLength(1);
    expect(rootPages[0].title).toBe("Standalone");
  });

  it("returns a folderMap keyed by external_id", () => {
    const folders = [
      { external_id: "f1", parent_id: null, name: "Design" },
      { external_id: "f2", parent_id: "f1", name: "Wireframes" },
    ];
    const { folderMap } = buildTree(folders, []);

    expect(folderMap.size).toBe(2);
    expect(folderMap.get("f1").name).toBe("Design");
    expect(folderMap.get("f2").name).toBe("Wireframes");
    expect(folderMap.get("f2").parent_id).toBe("f1");
  });

  it("treats pages with null folder_id as root pages", () => {
    const folders = [{ external_id: "f1", parent_id: null, name: "Notes" }];
    const pages = [
      { external_id: "p1", folder_id: null, title: "Root page" },
      { external_id: "p2", folder_id: undefined, title: "Also root" },
    ];
    const { rootPages } = buildTree(folders, pages);

    // undefined is falsy, so it also goes to root
    expect(rootPages).toHaveLength(2);
  });

  it("handles deeply nested folders (3 levels)", () => {
    const folders = [
      { external_id: "f1", parent_id: null, name: "A" },
      { external_id: "f2", parent_id: "f1", name: "B" },
      { external_id: "f3", parent_id: "f2", name: "C" },
    ];
    const pages = [{ external_id: "p1", folder_id: "f3", title: "Deep page" }];
    const { rootFolders } = buildTree(folders, pages);

    const levelA = rootFolders[0];
    const levelB = levelA.subfolders[0];
    const levelC = levelB.subfolders[0];

    expect(levelA.name).toBe("A");
    expect(levelB.name).toBe("B");
    expect(levelC.name).toBe("C");
    expect(levelC.pages).toHaveLength(1);
    expect(levelC.pages[0].title).toBe("Deep page");
  });

  it("handles pages with empty-string title by sorting them first", () => {
    const pages = [
      { external_id: "p1", folder_id: null, title: "Beta" },
      { external_id: "p2", folder_id: null, title: "" },
      { external_id: "p3", folder_id: null, title: "Alpha" },
    ];
    const { rootPages } = buildTree([], pages);

    // Empty string sorts before any letter
    expect(rootPages[0].title).toBe("");
    expect(rootPages[1].title).toBe("Alpha");
    expect(rootPages[2].title).toBe("Beta");
  });
});

// ---------------------------------------------------------------------------
// getFolderBreadcrumbs()
// ---------------------------------------------------------------------------

describe("getFolderBreadcrumbs", () => {
  it("returns empty array for null folderId", () => {
    const { folderMap } = buildTree([{ external_id: "f1", parent_id: null, name: "Design" }], []);
    expect(getFolderBreadcrumbs(null, folderMap)).toEqual([]);
  });

  it("returns empty array for undefined folderId", () => {
    const { folderMap } = buildTree([{ external_id: "f1", parent_id: null, name: "Design" }], []);
    expect(getFolderBreadcrumbs(undefined, folderMap)).toEqual([]);
  });

  it("returns empty array when folderMap is null", () => {
    expect(getFolderBreadcrumbs("f1", null)).toEqual([]);
  });

  it("returns single-element path for a root folder", () => {
    const { folderMap } = buildTree([{ external_id: "f1", parent_id: null, name: "Design" }], []);
    const crumbs = getFolderBreadcrumbs("f1", folderMap);

    expect(crumbs).toEqual([{ external_id: "f1", name: "Design" }]);
  });

  it("returns full ancestor chain for a nested folder (root → child → grandchild)", () => {
    const folders = [
      { external_id: "f1", parent_id: null, name: "Engineering" },
      { external_id: "f2", parent_id: "f1", name: "Backend" },
      { external_id: "f3", parent_id: "f2", name: "API" },
    ];
    const { folderMap } = buildTree(folders, []);
    const crumbs = getFolderBreadcrumbs("f3", folderMap);

    expect(crumbs).toEqual([
      { external_id: "f1", name: "Engineering" },
      { external_id: "f2", name: "Backend" },
      { external_id: "f3", name: "API" },
    ]);
  });

  it("returns empty array for a non-existent folderId", () => {
    const { folderMap } = buildTree([{ external_id: "f1", parent_id: null, name: "Design" }], []);
    expect(getFolderBreadcrumbs("nonexistent", folderMap)).toEqual([]);
  });

  it("returns breadcrumbs for a mid-level folder", () => {
    const folders = [
      { external_id: "f1", parent_id: null, name: "A" },
      { external_id: "f2", parent_id: "f1", name: "B" },
      { external_id: "f3", parent_id: "f2", name: "C" },
    ];
    const { folderMap } = buildTree(folders, []);
    const crumbs = getFolderBreadcrumbs("f2", folderMap);

    expect(crumbs).toEqual([
      { external_id: "f1", name: "A" },
      { external_id: "f2", name: "B" },
    ]);
  });
});
