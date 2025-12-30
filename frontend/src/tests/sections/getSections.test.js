/**
 * SECTION DEFINITION (Heading-Based)
 *
 * A "section" starts with a markdown heading (# to ######).
 *
 * Rules:
 * - A section starts at any line matching /^#{1,6}\s+/
 * - A section's scope extends until the next heading of equal or higher level
 *   (i.e., same or fewer # characters)
 * - Headings create a natural hierarchy: H2s nest inside H1s, H3s inside H2s, etc.
 *
 * Examples:
 * - H1 section ends at next H1 (or EOF)
 * - H2 section ends at next H1 or H2 (or EOF)
 * - H3 section ends at next H1, H2, or H3 (or EOF)
 */

import { getSections, findRootSectionAtPos, collectAllLinesInTree } from "../../getSections.js";
import { EditorState } from "@codemirror/state";

function createDocFromText(text) {
  return EditorState.create({ doc: text }).doc;
}

describe("getSections", () => {
  test("no headings returns empty", () => {
    const doc = createDocFromText("Hello world\nThis is a note");
    const { sections, tree } = getSections(doc);
    expect(sections).toEqual([]);
    expect(tree).toEqual([]);
  });

  test("empty document", () => {
    const doc = createDocFromText("");
    const { sections, tree } = getSections(doc);
    expect(sections).toEqual([]);
    expect(tree).toEqual([]);
  });

  test("single H1 heading", () => {
    const text = "# Main Title\nSome content\nMore content";
    const doc = createDocFromText(text);
    const { sections, tree } = getSections(doc);

    expect(sections.length).toBe(1);
    expect(sections[0].level).toBe(1);
    expect(sections[0].headingText).toBe("Main Title");
    expect(sections[0].line).toBe(1);
    expect(sections[0].to).toBe(text.length);

    expect(tree.length).toBe(1);
    expect(tree[0].children).toEqual([]);
  });

  test("two H1 headings", () => {
    const text = "# First\nContent 1\n# Second\nContent 2";
    const doc = createDocFromText(text);
    const { sections, tree } = getSections(doc);

    expect(sections.length).toBe(2);
    expect(sections[0].headingText).toBe("First");
    expect(sections[1].headingText).toBe("Second");

    const line3 = doc.line(3);
    expect(sections[0].to).toBe(line3.from - 1);

    expect(tree.length).toBe(2);
  });

  test("H1 with nested H2", () => {
    const text = "# Main\nIntro\n## Sub\nDetails";
    const doc = createDocFromText(text);
    const { sections, tree } = getSections(doc);

    expect(sections.length).toBe(2);
    expect(sections[0].level).toBe(1);
    expect(sections[1].level).toBe(2);

    expect(tree.length).toBe(1);
    expect(tree[0].children.length).toBe(1);
    expect(tree[0].children[0].headingText).toBe("Sub");
  });

  test("H1 with multiple nested H2s", () => {
    const text = "# Main\n## Sub1\nContent1\n## Sub2\nContent2";
    const doc = createDocFromText(text);
    const { sections, tree } = getSections(doc);

    expect(sections.length).toBe(3);
    expect(tree.length).toBe(1);
    expect(tree[0].children.length).toBe(2);
    expect(tree[0].children[0].headingText).toBe("Sub1");
    expect(tree[0].children[1].headingText).toBe("Sub2");
  });

  test("deep nesting H1 > H2 > H3", () => {
    const text = "# Level 1\n## Level 2\n### Level 3\nDeep content";
    const doc = createDocFromText(text);
    const { sections, tree } = getSections(doc);

    expect(sections.length).toBe(3);
    expect(tree.length).toBe(1);
    expect(tree[0].children.length).toBe(1);
    expect(tree[0].children[0].children.length).toBe(1);
    expect(tree[0].children[0].children[0].headingText).toBe("Level 3");
  });

  test("skipped levels H1 > H3 (no H2)", () => {
    const text = "# Main\n### Deep\nContent";
    const doc = createDocFromText(text);
    const { sections, tree } = getSections(doc);

    expect(sections.length).toBe(2);
    expect(tree.length).toBe(1);
    expect(tree[0].children.length).toBe(1);
    expect(tree[0].children[0].level).toBe(3);
  });

  test("sibling H1s with nested content", () => {
    const text = "# A\n## A1\n## A2\n# B\n## B1";
    const doc = createDocFromText(text);
    const { sections, tree } = getSections(doc);

    expect(sections.length).toBe(5);
    expect(tree.length).toBe(2);
    expect(tree[0].headingText).toBe("A");
    expect(tree[0].children.length).toBe(2);
    expect(tree[1].headingText).toBe("B");
    expect(tree[1].children.length).toBe(1);
  });

  test("H2 ends at next H1", () => {
    const text = "# First\n## Sub\nContent\n# Second";
    const doc = createDocFromText(text);
    const { sections } = getSections(doc);

    const subSection = sections.find((s) => s.headingText === "Sub");
    const line4 = doc.line(4);
    expect(subSection.to).toBe(line4.from - 1);
  });

  test("heading at end of document", () => {
    const text = "# Main\nContent\n## Last";
    const doc = createDocFromText(text);
    const { sections } = getSections(doc);

    const lastSection = sections.find((s) => s.headingText === "Last");
    expect(lastSection.to).toBe(text.length);
  });

  test("content before first heading is not in any section", () => {
    const text = "Preamble\n# Title\nContent";
    const doc = createDocFromText(text);
    const { sections } = getSections(doc);

    expect(sections.length).toBe(1);
    expect(sections[0].headingText).toBe("Title");
    expect(sections[0].line).toBe(2);
  });

  test("handles all heading levels", () => {
    const text = "# H1\n## H2\n### H3\n#### H4\n##### H5\n###### H6\nContent";
    const doc = createDocFromText(text);
    const { sections } = getSections(doc);

    expect(sections.length).toBe(6);
    expect(sections.map((s) => s.level)).toEqual([1, 2, 3, 4, 5, 6]);
  });

  test("invalid headings are ignored", () => {
    const text = "#NoSpace\n# Valid\n##Also Invalid";
    const doc = createDocFromText(text);
    const { sections } = getSections(doc);

    expect(sections.length).toBe(1);
    expect(sections[0].headingText).toBe("Valid");
  });
});

describe("findRootSectionAtPos", () => {
  test("finds root section for position in H1 content", () => {
    const text = "# Main\nContent here";
    const doc = createDocFromText(text);
    const { tree } = getSections(doc);

    const pos = text.indexOf("Content");
    const root = findRootSectionAtPos(tree, pos);

    expect(root).not.toBeNull();
    expect(root.headingText).toBe("Main");
  });

  test("finds root H1 for position in nested H2", () => {
    const text = "# Main\n## Sub\nNested content";
    const doc = createDocFromText(text);
    const { tree } = getSections(doc);

    const pos = text.indexOf("Nested");
    const root = findRootSectionAtPos(tree, pos);

    expect(root).not.toBeNull();
    expect(root.headingText).toBe("Main");
    expect(root.level).toBe(1);
  });

  test("returns null for position before any heading", () => {
    const text = "Preamble\n# Title";
    const doc = createDocFromText(text);
    const { tree } = getSections(doc);

    const pos = 0;
    const root = findRootSectionAtPos(tree, pos);

    expect(root).toBeNull();
  });

  test("distinguishes between sibling root sections", () => {
    const text = "# A\nContent A\n# B\nContent B";
    const doc = createDocFromText(text);
    const { tree } = getSections(doc);

    const posA = text.indexOf("Content A");
    const posB = text.indexOf("Content B");

    expect(findRootSectionAtPos(tree, posA).headingText).toBe("A");
    expect(findRootSectionAtPos(tree, posB).headingText).toBe("B");
  });
});

describe("collectAllLinesInTree", () => {
  test("collects all lines for simple section", () => {
    const text = "# Title\nLine 2\nLine 3";
    const doc = createDocFromText(text);
    const { tree } = getSections(doc);

    const lines = collectAllLinesInTree(tree[0], doc);

    expect(lines.has(1)).toBe(true);
    expect(lines.has(2)).toBe(true);
    expect(lines.has(3)).toBe(true);
    expect(lines.size).toBe(3);
  });

  test("collects lines including nested sections", () => {
    const text = "# Main\nIntro\n## Sub\nDetails";
    const doc = createDocFromText(text);
    const { tree } = getSections(doc);

    const lines = collectAllLinesInTree(tree[0], doc);

    expect(lines.size).toBe(4);
    expect(lines.has(1)).toBe(true);
    expect(lines.has(2)).toBe(true);
    expect(lines.has(3)).toBe(true);
    expect(lines.has(4)).toBe(true);
  });

  test("does not include sibling sections", () => {
    const text = "# A\nContent A\n# B\nContent B";
    const doc = createDocFromText(text);
    const { tree } = getSections(doc);

    const linesA = collectAllLinesInTree(tree[0], doc);
    const linesB = collectAllLinesInTree(tree[1], doc);

    expect(linesA.has(1)).toBe(true);
    expect(linesA.has(2)).toBe(true);
    expect(linesA.has(3)).toBe(false);
    expect(linesA.has(4)).toBe(false);

    expect(linesB.has(1)).toBe(false);
    expect(linesB.has(2)).toBe(false);
    expect(linesB.has(3)).toBe(true);
    expect(linesB.has(4)).toBe(true);
  });
});
