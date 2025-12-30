import { foldEffect, unfoldEffect, foldedRanges } from "@codemirror/language";
import { findSectionFold } from "./findSectionFold.js";

const STORAGE_PREFIX = "page-folds-";

function getStorageKey(pageId) {
  return `${STORAGE_PREFIX}${pageId}`;
}

export function saveFoldedRanges(view, pageId) {
  if (!pageId) return;

  const doc = view.state.doc;
  const foldedLineNumbers = [];
  const iter = foldedRanges(view.state).iter();

  while (iter.value) {
    const lineNum = doc.lineAt(iter.from).number;
    foldedLineNumbers.push(lineNum);
    iter.next();
  }

  if (foldedLineNumbers.length > 0) {
    localStorage.setItem(getStorageKey(pageId), JSON.stringify(foldedLineNumbers));
  } else {
    localStorage.removeItem(getStorageKey(pageId));
  }
}

export function restoreFoldedRanges(view, pageId) {
  if (!pageId) return;

  const stored = localStorage.getItem(getStorageKey(pageId));
  if (!stored) return;

  try {
    const lineNumbers = JSON.parse(stored);
    const doc = view.state.doc;
    const effects = [];

    for (const lineNum of lineNumbers) {
      if (lineNum > 0 && lineNum <= doc.lines) {
        const line = doc.line(lineNum);
        const foldRange = findSectionFold(view.state, line.from, line.to);
        if (foldRange) {
          effects.push(foldEffect.of({ from: foldRange.from, to: foldRange.to }));
        }
      }
    }

    if (effects.length > 0) {
      view.dispatch({ effects });
    }
  } catch (e) {
    console.warn("Failed to restore fold state:", e);
    localStorage.removeItem(getStorageKey(pageId));
  }
}

export function clearFoldStorage(pageId) {
  if (pageId) {
    localStorage.removeItem(getStorageKey(pageId));
  }
}
