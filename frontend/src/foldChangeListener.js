import { ViewPlugin } from "@codemirror/view";
import { foldEffect, unfoldEffect } from "@codemirror/language";
import { saveFoldedRanges } from "./foldPersistence.js";

let currentPageId = null;

export function setCurrentPageIdForFolds(pageId) {
  currentPageId = pageId;
}

export const foldChangeListener = ViewPlugin.fromClass(
  class {
    update(update) {
      if (!currentPageId) return;

      for (const tr of update.transactions) {
        for (const effect of tr.effects) {
          if (effect.is(foldEffect) || effect.is(unfoldEffect)) {
            saveFoldedRanges(update.view, currentPageId);
            return;
          }
        }
      }
    }
  }
);
