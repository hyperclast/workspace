/**
 * @param {Text} doc - CodeMirror state.doc (Text object)
 * @returns {Array<{ from: number, to: number, line: number }>}
 */
export function getSections(doc) {
  const sections = [];
  const lineCount = doc.lines;

  let i = 1;

  while (i <= lineCount) {
    const line = doc.line(i);
    const text = line.text.trim();

    if (text === "") {
      i++;
      continue;
    }

    const sectionStart = line.from;
    const sectionLine = i;

    let j = i + 1;
    let blankStreak = 0;

    while (j <= lineCount) {
      const nextLine = doc.line(j);
      if (nextLine.text.trim() === "") {
        blankStreak++;
        if (blankStreak === 2) break;
      } else {
        blankStreak = 0;
      }
      j++;
    }

    // Clamp j - blankStreak to valid range (lines are 1-indexed)
    const lastLineNum = Math.max(1, Math.min(j - blankStreak, lineCount));
    const sectionEnd = doc.line(lastLineNum).to;

    sections.push({ from: sectionStart, to: sectionEnd, line: sectionLine });
    i = j;
  }

  return sections;
}
