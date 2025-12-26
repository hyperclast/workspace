import { getSections } from "./getSections.js";

export function findSectionFold(state, lineStart) {
  const doc = state.doc;
  const sections = getSections(doc);

  for (const section of sections) {
    const line = doc.lineAt(lineStart);
    if (line.number === section.line) {
      if (section.to > line.to + 1) {
        return { from: line.to, to: section.to };
      }
    }
  }

  return null;
}
