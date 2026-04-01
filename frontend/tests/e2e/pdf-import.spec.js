/**
 * End-to-end tests for PDF import.
 *
 * Tests:
 * 1. Import PDF via API creates a page with extracted text and a PDF link
 * 2. The extracted text is discussable (comments anchor correctly)
 * 3. Non-PDF files are rejected with 400
 * 4. The page title is derived from the filename
 *
 * Run with:
 *   npx playwright test pdf-import.spec.js --headed
 */

import { test, expect } from "@playwright/test";
import { dismissSocratesPanel, waitForEditorContent } from "./helpers.js";
import path from "path";
import fs from "fs";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";
const TEST_EMAIL = process.env.TEST_EMAIL || "dev@localhost";
const TEST_PASSWORD = process.env.TEST_PASSWORD || "dev";

const SAMPLE_PDF = path.resolve(import.meta.dirname, "fixtures/sample.pdf");

// Pre-extracted text matching the fixture PDF content.
// In production, PDF.js extracts this client-side. In tests we send it directly.
const SAMPLE_TITLE = "sample";
const SAMPLE_CONTENT = [
  "# Page 1",
  "",
  "Introduction to Machine Learning",
  "Machine learning is a subset of artificial intelligence that provides",
  "systems the ability to automatically learn and improve from experience",
  "without being explicitly programmed.",
  "",
  "# Page 2",
  "",
  "Supervised Learning",
  "In supervised learning, the algorithm is trained on labeled data.",
  "The model learns to map inputs to outputs based on example pairs.",
  "",
  "Unsupervised Learning",
  "Unsupervised learning uses unlabeled data to discover hidden patterns.",
  "Common techniques include clustering and dimensionality reduction.",
].join("\n");

async function login(page) {
  await page.goto(`${BASE_URL}/login`);
  await page.waitForSelector("#login-email", { timeout: 10000 });
  await page.fill("#login-email", TEST_EMAIL);
  await page.fill("#login-password", TEST_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForSelector("#editor", { timeout: 20000 });
  await page.waitForSelector(".cm-content", { timeout: 10000 });
  await dismissSocratesPanel(page);
}

async function getFirstProjectId(page) {
  await page.waitForSelector(".sidebar-project[data-project-id]", {
    timeout: 10000,
  });
  return page.locator(".sidebar-project[data-project-id]").first().getAttribute("data-project-id");
}

/**
 * Import a PDF via the API. Sends pre-extracted text (mimicking what PDF.js
 * would produce client-side) alongside the original PDF file.
 */
async function importPdfViaApi(page, projectId, opts = {}) {
  const cookies = await page.context().cookies();
  const csrfCookie = cookies.find((c) => c.name === "csrftoken");
  const sessionCookie = cookies.find((c) => c.name === "sessionid");

  const apiContext = page.context().request;
  const response = await apiContext.post(`${BASE_URL}/api/v1/imports/pdf/`, {
    multipart: {
      project_id: projectId,
      title: opts.title || SAMPLE_TITLE,
      content: opts.content || SAMPLE_CONTENT,
      file: {
        name: opts.fileName || "sample.pdf",
        mimeType: opts.mimeType || "application/pdf",
        buffer: opts.buffer || fs.readFileSync(SAMPLE_PDF),
      },
    },
    headers: {
      "X-CSRFToken": csrfCookie.value,
      Cookie: `csrftoken=${csrfCookie.value}; sessionid=${sessionCookie.value}`,
    },
  });

  return { response, status: response.status(), data: await response.json() };
}

test.describe("PDF Import", () => {
  test.setTimeout(120000);

  test("import PDF creates page with extracted text and PDF link", async ({ page }) => {
    await login(page);

    const projectId = await getFirstProjectId(page);
    expect(projectId).toBeTruthy();

    const { status, data } = await importPdfViaApi(page, projectId);

    expect(status).toBe(201);
    expect(data.page_external_id).toBeTruthy();
    expect(data.page_title).toBe("sample");
    expect(data.file_external_id).toBeTruthy();
    expect(data.file_download_url).toContain("/files/");

    // Navigate to the created page
    await page.goto(`${BASE_URL}/pages/${data.page_external_id}/`);
    await page.waitForSelector(".cm-content", { timeout: 15000 });

    await page.waitForFunction(
      () => (window.editorView?.state?.doc?.toString() || "").length > 50,
      { timeout: 15000 }
    );

    const editorContent = await page.evaluate(
      () => window.editorView?.state?.doc?.toString() || ""
    );

    // Verify extracted text
    expect(editorContent).toContain("Machine learning");
    expect(editorContent).toContain("Supervised Learning");
    expect(editorContent).toContain("Unsupervised Learning");

    // Verify PDF link at top
    expect(editorContent).toContain("sample.pdf");
    expect(editorContent).toContain("/files/");

    // Verify page separators
    expect(editorContent).toContain("# Page 1");
    expect(editorContent).toContain("# Page 2");

    console.log("PASSED: PDF import creates page with extracted text");
  });

  test("imported PDF page supports comments and discuss", async ({ page }) => {
    await login(page);

    const projectId = await getFirstProjectId(page);
    const { status, data } = await importPdfViaApi(page, projectId);
    expect(status).toBe(201);

    await page.goto(`${BASE_URL}/pages/${data.page_external_id}/`);
    await page.waitForSelector(".cm-content", { timeout: 15000 });

    // Wait for editor content to load (don't block on collab sync — the app
    // renders REST content first and upgrades to collaboration later)
    await waitForEditorContent(page, "Machine learning", 20000);

    // Select text and add a comment
    await page.evaluate(() => {
      const view = window.editorView;
      const content = view.state.doc.toString();
      const idx = content.indexOf("Machine learning");
      if (idx === -1) throw new Error("Text not found");
      view.dispatch({
        selection: { anchor: idx, head: idx + "Machine learning".length },
        scrollIntoView: true,
      });
      view.focus();
    });

    const popoverBtn = page.locator(".cm-comment-popover-button button");
    await expect(popoverBtn).toBeVisible({ timeout: 5000 });
    await popoverBtn.click();

    const textarea = page.locator(".cm-comment-popover-textarea");
    await expect(textarea).toBeVisible({ timeout: 5000 });
    await textarea.fill("What types of ML are discussed here?");
    await page.locator(".cm-comment-popover-submit").click();

    await page.waitForTimeout(1000);

    await page.locator('button.sidebar-tab[data-tab="comments"]').click();

    const commentBody = page.locator(".comment-body");
    await expect(commentBody.first()).toContainText("What types of ML", {
      timeout: 10000,
    });

    const commentBar = page.locator(".cm-comment-bar");
    await expect(commentBar.first()).toBeVisible({ timeout: 5000 });

    console.log("PASSED: comments work on imported PDF page");
  });

  test("importing non-PDF file returns 400", async ({ page }) => {
    await login(page);

    const projectId = await getFirstProjectId(page);

    const { status, data } = await importPdfViaApi(page, projectId, {
      fileName: "not-a-pdf.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("This is not a PDF file"),
      title: "not a pdf",
      content: "some content",
    });

    expect(status).toBe(400);
    expect(data.error).toBe("invalid_content_type");

    console.log("PASSED: non-PDF file rejected with 400");
  });

  test("empty content is rejected", async ({ page }) => {
    await login(page);

    const projectId = await getFirstProjectId(page);

    const { status, data } = await importPdfViaApi(page, projectId, {
      title: "empty pdf",
      content: "   ",
    });

    expect(status).toBe(400);
    expect(data.error).toBe("no_content");

    console.log("PASSED: empty content rejected with 400");
  });

  test("import PDF via sidenav menu creates page and navigates to it", async ({ page }) => {
    await login(page);

    // Open the project menu in the sidenav
    const menuBtn = page.locator(".project-menu-btn").first();
    await menuBtn.click();

    // Wait for menu dropdown to open
    const dropdown = page.locator(".project-menu-dropdown.open");
    await expect(dropdown).toBeVisible({ timeout: 3000 });

    // Find and click "Import > PDF"
    const pdfImportBtn = dropdown.locator("button.project-menu-item", {
      hasText: "PDF",
    });
    await expect(pdfImportBtn).toBeVisible({ timeout: 3000 });

    // Set up a file chooser listener BEFORE clicking the button
    const fileChooserPromise = page.waitForEvent("filechooser");
    await pdfImportBtn.click();

    // Provide the PDF file to the file picker
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(SAMPLE_PDF);

    // Wait for navigation to the new page (the handler does window.location.href = ...)
    await page.waitForURL(/\/pages\/[A-Za-z0-9]+/, { timeout: 30000 });
    await page.waitForSelector(".cm-content", { timeout: 15000 });

    // Wait for content to load
    await page.waitForFunction(
      () => (window.editorView?.state?.doc?.toString() || "").length > 50,
      { timeout: 15000 }
    );

    const editorContent = await page.evaluate(
      () => window.editorView?.state?.doc?.toString() || ""
    );

    // Verify extracted text from the PDF made it into the page
    expect(editorContent).toContain("Machine learning");
    expect(editorContent).toContain("/files/");

    console.log("PASSED: sidenav PDF import creates page and navigates");
  });
});
