import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  renderList,
  updateActiveItem,
  setNavigateHandler,
  setNewPageHandler,
} from "../../sidenav/list.js";

describe("Project List Rendering", () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="sidebar-list"></div>';
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("renders projects with nested pages", () => {
    const projects = [
      {
        external_id: "proj1",
        name: "Project 1",
        org: { external_id: "org1", name: "Org 1" },
        pages: [
          { external_id: "page1", title: "Page 1" },
          { external_id: "page2", title: "Page 2" },
        ],
      },
    ];

    renderList(projects, null);

    const projectEl = document.querySelector('.sidebar-project[data-project-id="proj1"]');
    expect(projectEl).not.toBeNull();

    const pageEls = document.querySelectorAll(".sidebar-item");
    expect(pageEls.length).toBe(2);
  });

  it("shows empty state when no projects", () => {
    renderList([], null);

    const emptyEl = document.querySelector(".sidebar-empty");
    expect(emptyEl).not.toBeNull();
    expect(emptyEl.textContent).toContain("No projects");
  });

  it("marks active page correctly", () => {
    const projects = [
      {
        external_id: "proj1",
        name: "Project 1",
        org: { external_id: "org1", name: "Org 1" },
        pages: [
          { external_id: "page1", title: "Page 1" },
          { external_id: "page2", title: "Page 2" },
        ],
      },
    ];

    renderList(projects, "page2");

    const activePage = document.querySelector('.sidebar-item[data-external-id="page2"]');
    expect(activePage.classList.contains("active")).toBe(true);

    const inactivePage = document.querySelector('.sidebar-item[data-external-id="page1"]');
    expect(inactivePage.classList.contains("active")).toBe(false);
  });

  it("calls navigate handler when page clicked", () => {
    const navigateHandler = vi.fn();
    setNavigateHandler(navigateHandler);

    const projects = [
      {
        external_id: "proj1",
        name: "Project 1",
        org: { external_id: "org1", name: "Org 1" },
        pages: [{ external_id: "page1", title: "Page 1" }],
      },
    ];

    renderList(projects, null);

    const pageEl = document.querySelector('.sidebar-item[data-external-id="page1"]');
    pageEl.click();

    expect(navigateHandler).toHaveBeenCalledWith("page1");
  });

  it("calls new page handler when button clicked", () => {
    const newPageHandler = vi.fn();
    setNewPageHandler(newPageHandler);

    const projects = [
      {
        external_id: "proj1",
        name: "Project 1",
        org: { external_id: "org1", name: "Org 1" },
        pages: [],
      },
    ];

    renderList(projects, null);

    const newPageBtn = document.querySelector('.sidebar-new-page-btn[data-project-id="proj1"]');
    newPageBtn.click();

    expect(newPageHandler).toHaveBeenCalledWith("proj1");
  });

  it("shows org name only when multiple orgs exist", () => {
    // Single org - should NOT show org name
    const singleOrgProjects = [
      {
        external_id: "proj1",
        name: "Project 1",
        org: { external_id: "org1", name: "Org 1" },
        pages: [],
      },
    ];

    renderList(singleOrgProjects, null);
    expect(document.querySelector(".project-org")).toBeNull();

    // Multiple orgs - should show org name
    const multiOrgProjects = [
      {
        external_id: "proj1",
        name: "Project 1",
        org: { external_id: "org1", name: "Org 1" },
        pages: [],
      },
      {
        external_id: "proj2",
        name: "Project 2",
        org: { external_id: "org2", name: "Org 2" },
        pages: [],
      },
    ];

    renderList(multiOrgProjects, null);
    const orgLabels = document.querySelectorAll(".project-org");
    expect(orgLabels.length).toBe(2);
  });

  it("escapes HTML in project and page names", () => {
    const projects = [
      {
        external_id: "proj1",
        name: "<script>alert('xss')</script>",
        org: { external_id: "org1", name: "Org 1" },
        pages: [{ external_id: "page1", title: "<img src=x onerror=alert('xss')>" }],
      },
    ];

    renderList(projects, null);

    // Check that script tags are escaped, not executed
    const projectName = document.querySelector(".project-name");
    expect(projectName.innerHTML).not.toContain("<script>");

    const pageTitle = document.querySelector(".page-title");
    expect(pageTitle.innerHTML).not.toContain("<img");
  });
});

describe("updateActiveItem", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="sidebar-list">
        <div class="sidebar-item" data-external-id="page1"></div>
        <div class="sidebar-item active" data-external-id="page2"></div>
        <div class="sidebar-item" data-external-id="page3"></div>
      </div>
    `;
  });

  it("updates active state correctly", () => {
    updateActiveItem("page3");

    expect(document.querySelector('[data-external-id="page1"]').classList.contains("active")).toBe(
      false
    );
    expect(document.querySelector('[data-external-id="page2"]').classList.contains("active")).toBe(
      false
    );
    expect(document.querySelector('[data-external-id="page3"]').classList.contains("active")).toBe(
      true
    );
  });
});
