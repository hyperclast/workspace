/**
 * End-to-end tests for PDF import.
 *
 * Imported PDFs land as PDF-native pages (filetype="pdf", schema_version=2):
 * the original PDF renders inline via PdfPageView and there is no CodeMirror
 * editor on the page. Extracted text is stored on `page.details.extracted_text`
 * (used for search and AI context) and is verified here via the page-details
 * API rather than via editor doc contents.
 *
 * Selection-driven comment flow on PDF pages is covered by pdf-pages.spec.js,
 * which intentionally skips scripted text selection (PDF.js text layer spans
 * don't selection-emulate cleanly in headless mode).
 *
 * Run with:
 *   npx playwright test pdf-import.spec.js --headed
 */

import { test, expect } from "@playwright/test";
import { waitForLoggedIn } from "./helpers.js";
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
  await waitForLoggedIn(page);
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

  test("import PDF creates a PDF-native page with extracted text stored server-side", async ({
    page,
  }) => {
    await login(page);

    const projectId = await getFirstProjectId(page);
    expect(projectId).toBeTruthy();

    const { status, data } = await importPdfViaApi(page, projectId);

    expect(status).toBe(201);
    expect(data.page_external_id).toBeTruthy();
    expect(data.page_title).toBe("sample");
    expect(data.file_external_id).toBeTruthy();
    expect(data.file_download_url).toContain("/files/");

    // Navigate to the created page — PDF-native pages mount PdfPageView, not
    // CodeMirror, so we wait for `.pdf-page-view` and then for the first
    // rasterized page wrapper.
    await page.goto(`${BASE_URL}/pages/${data.page_external_id}/`);
    await page.waitForSelector(".pdf-page-view", { timeout: 20000 });
    await page.waitForSelector('[data-pdf-page="1"]', { timeout: 15000 });

    // Sanity: a PDF-native page must NOT mount CodeMirror.
    await expect(page.locator(".cm-content")).toHaveCount(0);

    // Verify the page is wired up as a PDF-native page and the extracted text
    // landed in `details.extracted_text` (used by search and AI context).
    const pageResp = await page
      .context()
      .request.get(`${BASE_URL}/api/v1/pages/${data.page_external_id}/`);
    expect(pageResp.status()).toBe(200);
    const pageData = await pageResp.json();

    expect(pageData.details.filetype).toBe("pdf");
    expect(pageData.details.schema_version).toBe(2);
    expect(pageData.details.pdf_file_id).toBe(data.file_external_id);

    const extracted = pageData.details.extracted_text || "";
    expect(extracted).toContain("Machine learning");
    expect(extracted).toContain("Supervised Learning");
    expect(extracted).toContain("Unsupervised Learning");
    expect(extracted).toContain("# Page 1");
    expect(extracted).toContain("# Page 2");

    console.log("PASSED: PDF import creates PDF-native page with extracted text");
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

    // PDF-native pages mount PdfPageView, not CodeMirror.
    await page.waitForSelector(".pdf-page-view", { timeout: 20000 });
    await page.waitForSelector('[data-pdf-page="1"]', { timeout: 15000 });

    const pageId = page.url().match(/\/pages\/([A-Za-z0-9]+)/)?.[1];
    expect(pageId).toBeTruthy();

    // Verify the extracted text landed server-side via the page-details API.
    const pageResp = await page.context().request.get(`${BASE_URL}/api/v1/pages/${pageId}/`);
    expect(pageResp.status()).toBe(200);
    const pageData = await pageResp.json();

    expect(pageData.details.filetype).toBe("pdf");
    expect(pageData.details.pdf_file_id).toBeTruthy();
    expect(pageData.details.extracted_text || "").toContain("Machine learning");

    console.log("PASSED: sidenav PDF import creates PDF-native page and navigates");
  });
});
