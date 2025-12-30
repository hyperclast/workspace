const HEADING_REGEX = /^(#{1,6})\s+(.*)$/;

function parseHeadingLevel(lineText) {
  const match = lineText.match(HEADING_REGEX);
  if (match) {
    return { level: match[1].length, text: match[2] };
  }
  return null;
}

/**
 * @param {Text} doc - CodeMirror state.doc (Text object)
 * @returns {{ sections: Array<{ from: number, to: number, line: number, level: number, headingText: string }>, tree: Array }}
 */
export function getSections(doc) {
  const lineCount = doc.lines;
  const headings = [];

  for (let i = 1; i <= lineCount; i++) {
    const line = doc.line(i);
    const parsed = parseHeadingLevel(line.text);
    if (parsed) {
      headings.push({
        from: line.from,
        line: i,
        level: parsed.level,
        headingText: parsed.text,
      });
    }
  }

  if (headings.length === 0) {
    return { sections: [], tree: [] };
  }

  const sections = [];
  for (let i = 0; i < headings.length; i++) {
    const heading = headings[i];
    let sectionEnd;

    let j = i + 1;
    while (j < headings.length) {
      if (headings[j].level <= heading.level) {
        break;
      }
      j++;
    }

    if (j < headings.length) {
      const nextSameLevelLine = doc.line(headings[j].line);
      const prevLineNum = headings[j].line - 1;
      if (prevLineNum >= 1) {
        sectionEnd = doc.line(prevLineNum).to;
      } else {
        sectionEnd = heading.from;
      }
    } else {
      sectionEnd = doc.line(lineCount).to;
    }

    sections.push({
      from: heading.from,
      to: sectionEnd,
      line: heading.line,
      level: heading.level,
      headingText: heading.headingText,
    });
  }

  const tree = buildTree(sections);

  return { sections, tree };
}

function buildTree(sections) {
  const tree = [];
  const stack = [];

  for (const section of sections) {
    const node = { ...section, children: [] };

    while (stack.length > 0 && stack[stack.length - 1].level >= section.level) {
      stack.pop();
    }

    if (stack.length === 0) {
      tree.push(node);
    } else {
      stack[stack.length - 1].children.push(node);
    }

    stack.push(node);
  }

  return tree;
}

export function findRootSectionAtPos(tree, pos) {
  for (const root of tree) {
    if (pos >= root.from && pos <= root.to) {
      return root;
    }
  }
  return null;
}

export function collectAllLinesInTree(node, doc) {
  const lines = new Set();

  function traverse(n) {
    const startLine = doc.lineAt(n.from).number;
    const endLine = doc.lineAt(n.to).number;
    for (let i = startLine; i <= endLine; i++) {
      lines.add(i);
    }
    for (const child of n.children) {
      traverse(child);
    }
  }

  traverse(node);
  return lines;
}

export function findSectionAtLine(sections, lineNumber) {
  for (const section of sections) {
    if (section.line === lineNumber) {
      return section;
    }
  }
  return null;
}
