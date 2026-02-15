/**
 * Test fixtures for visual regression testing.
 *
 * These markdown content strings cover all visual elements that need testing.
 */

export const FIXTURES = {
  /**
   * Mixed content covering all major formatting types.
   */
  mixedContent: `# Document Title

Regular paragraph with **bold text** and __underlined text__.

## Section with Lists

- Bullet item one
- Bullet item two
  - Nested bullet
    - Deeply nested

1. Ordered item
2. Second ordered

## Checkboxes

- [ ] Unchecked task
- [x] Completed task
  - [ ] Nested unchecked
  - [x] Nested checked

## Links

Check [Internal Link](/pages/abc123/) and [External Link](https://example.com).

## Code

Inline \`code\` and:

\`\`\`javascript
function example() {
  return "hello";
}
\`\`\`

## Blockquote

> This is a blockquote
> with multiple lines

## Table

| Column A | Column B | Column C |
|----------|----------|----------|
| Data 1   | Data 2   | Data 3   |
| Row 2 A  | Row 2 B  | Row 2 C  |

---

Final paragraph after horizontal rule.`,

  /**
   * Deep nesting to test indent consistency.
   */
  deepNesting: `# Deep Nesting Test

- Level 0
  - Level 1
    - Level 2
      - Level 3
        - Level 4
          - Level 5

- [ ] L0 checkbox
  - [ ] L1 checkbox
    - [ ] L2 checkbox
      - [x] L3 checked
        - [ ] L4 unchecked

1. Ordered L0
   1. Ordered L1
      1. Ordered L2
         1. Ordered L3`,

  /**
   * List alignment test - bullets, checkboxes, and ordered at same level.
   */
  listAlignment: `# List Alignment Test

- Bullet item one
- Bullet item two
- Bullet item three

- [ ] Checkbox one
- [ ] Checkbox two
- [x] Checkbox three

1. Ordered one
2. Ordered two
3. Ordered three

Paragraph text after lists should align with list item text.`,

  /**
   * Complex tables to test column alignment.
   */
  tablesComplex: `# Complex Table Test

| Name | Age | City | Country | Status |
|------|-----|------|---------|--------|
| Alice | 30 | NYC | USA | Active |
| Bob | 25 | London | UK | Inactive |
| Charlie | 35 | Tokyo | Japan | Active |
| Diana | 28 | Paris | France | Pending |

Simple table:

| A | B | C |
|---|---|---|
| X | Y | Z |`,

  /**
   * Various link types.
   */
  linksVariety: `# Link Styling Test

Paragraph with [page link](/pages/abc123/) inline.

- List with [internal](/pages/def456/) link
- And [external](https://example.com) link

> Blockquote with [link](/pages/ghi789/)

Multiple adjacent: [one](/pages/a/) [two](/pages/b/) [three](https://c.com)

Regular text with no links for comparison.`,

  /**
   * All heading levels.
   */
  headingsAll: `# Heading 1

Content under H1.

## Heading 2

Content under H2.

### Heading 3

Content under H3.

#### Heading 4

Content under H4.

##### Heading 5

Content under H5.

###### Heading 6

Content under H6.`,

  /**
   * Spacing between different element types.
   */
  spacingTest: `# Spacing Test

Paragraph one.
Paragraph two.
Paragraph three.

- Bullet after paragraph

> Blockquote after bullet

Regular text after blockquote.

## Heading after paragraph

More text after heading.`,

  /**
   * Blockquotes with various content.
   */
  blockquotes: `# Blockquote Test

> Single line blockquote

> Multi-line blockquote
> continues on second line
> and third line

> Blockquote with **bold** and [link](/pages/x/)

Regular paragraph after blockquotes.

- List item
> Blockquote after list`,

  /**
   * Code blocks and inline code.
   */
  codeBlocks: `# Code Test

Inline \`code\` in a paragraph.

\`\`\`javascript
// Code block
function test() {
  return true;
}
\`\`\`

\`\`\`python
# Python code
def hello():
    print("world")
\`\`\`

Text after code blocks.`,
};

/**
 * Helper to get all fixture keys.
 */
export function getFixtureKeys() {
  return Object.keys(FIXTURES);
}

/**
 * Login helper for tests.
 */
export async function login(page, baseUrl) {
  const url = baseUrl || process.env.TEST_BASE_URL || "http://localhost:9800";
  const email = process.env.TEST_EMAIL || "dev@localhost";
  const password = process.env.TEST_PASSWORD || "dev";

  await page.goto(`${url}/login`);
  await page.waitForSelector("#login-email", { timeout: 10000 });
  await page.fill("#login-email", email);
  await page.fill("#login-password", password);
  await page.click('button[type="submit"]');
  await page.waitForSelector("#editor", { timeout: 20000 });
  await page.waitForSelector(".cm-content", { timeout: 10000 });
}

/**
 * Create a new test page and insert content.
 */
export async function setupTestPage(page, content, pageName = "Visual Test") {
  // At narrow viewports (≤1024px), the sidebar is hidden — open it first
  const viewport = page.viewportSize();
  if (viewport && viewport.width <= 1024) {
    const sidebarToggle = page.locator("#sidebar-toggle");
    await sidebarToggle.click();
    await page.waitForTimeout(300);
  }

  // Click new page button
  const newPageBtn = page.locator(".sidebar-new-page-btn").first();
  await newPageBtn.click();

  // Handle modal
  const modal = page.locator(".modal");
  await modal.waitFor({ state: "visible", timeout: 5000 });

  const titleInput = page.locator("#page-title-input");
  await titleInput.fill(pageName);

  const createBtn = page.locator(".modal-btn-primary");
  await createBtn.click();

  // Wait for editor
  await page.waitForSelector(".cm-content", { timeout: 10000 });
  await page.waitForTimeout(500);

  // At narrow viewports, close the sidebar overlay so it doesn't block the editor.
  // Click the backdrop (#sidebar-overlay) instead of #sidebar-toggle, because
  // the open sidebar (z-index: 1000) covers the toggle button at this width.
  if (viewport && viewport.width <= 1024) {
    const overlay = page.locator("#sidebar-overlay.visible");
    if (await overlay.isVisible({ timeout: 1000 }).catch(() => false)) {
      await overlay.click();
      await page.waitForTimeout(300);
    }
  }

  // Insert content
  const editor = page.locator(".cm-content");
  await editor.click();
  await editor.fill(content);

  // Move cursor away for clean rendering
  await page.keyboard.press("Control+Home");
  await page.waitForTimeout(500);

  return editor;
}
