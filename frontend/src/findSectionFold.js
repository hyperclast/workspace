import { getSections } from "./getSections.js";
import { SECTION_SCAN_LIMIT_LINES } from "./config/performance.js";

/**
 * WeakMap cache for section data, keyed by document object.
 * This ensures:
 * - Each editor instance has its own cache
 * - Cache is automatically garbage collected when document is disposed
 * - No cross-contamination between multiple open documents
 */
const sectionCache = new WeakMap();

function getCachedSections(doc) {
  if (doc.lines > SECTION_SCAN_LIMIT_LINES) {
    return [];
  }

  let cached = sectionCache.get(doc);
  if (!cached) {
    cached = getSections(doc).sections;
    sectionCache.set(doc, cached);
  }
  return cached;
}

export function findSectionFold(state, lineStart) {
  const doc = state.doc;
  const sections = getCachedSections(doc);

  const line = doc.lineAt(lineStart);
  for (const section of sections) {
    if (line.number === section.line) {
      if (section.to > line.to) {
        return { from: line.to, to: section.to };
      }
    }
  }

  return null;
}
