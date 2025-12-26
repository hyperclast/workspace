import { autocompletion } from "@codemirror/autocomplete";
import { csrfFetch } from "./csrf.js";

const API_BASE = "/api";

let debounceTimeout = null;
let cachedPages = null;
let lastQuery = "";

async function fetchAutocompletePages(query) {
  const response = await csrfFetch(`${API_BASE}/pages/autocomplete/?q=${encodeURIComponent(query)}`);
  if (!response.ok) {
    throw new Error("Failed to fetch pages for autocomplete");
  }
  const data = await response.json();
  return data.pages || [];
}

function findLinkContext(state, pos) {
  const line = state.doc.lineAt(pos);
  const textBefore = line.text.slice(0, pos - line.from);
  const textAfter = line.text.slice(pos - line.from);

  const linkMatch = textBefore.match(/\[([^\]]*)\]\(([^)]*)?$/);
  if (linkMatch) {
    const linkTextStart = line.from + textBefore.lastIndexOf("[" + linkMatch[1] + "]");
    const urlStart = linkTextStart + linkMatch[1].length + 3;
    const currentUrl = linkMatch[2] || "";
    let toPos = pos;
    const closingMatch = textAfter.match(/^[^)]*\)/);
    if (closingMatch) {
      toPos = pos + closingMatch[0].length;
    }
    return {
      type: "url",
      linkText: linkMatch[1],
      currentUrl,
      urlStart,
      from: urlStart,
      to: toPos,
    };
  }

  const textMatch = textBefore.match(/\[([^\]]*)$/);
  if (textMatch) {
    const textStart = line.from + textBefore.lastIndexOf("[");
    let toPos = pos;
    const trailingMatch = textAfter.match(/^\]\([^)]*\)/);
    if (trailingMatch) {
      toPos = pos + trailingMatch[0].length;
    }
    return {
      type: "text",
      currentText: textMatch[1],
      from: textStart + 1,
      to: toPos,
      hasTrailingLink: !!trailingMatch,
    };
  }

  return null;
}

async function linkCompletionSource(context) {
  const linkContext = findLinkContext(context.state, context.pos);

  if (!linkContext) {
    return null;
  }

  const query = linkContext.type === "url"
    ? linkContext.linkText
    : linkContext.currentText;

  if (query !== lastQuery || !cachedPages) {
    lastQuery = query;

    if (debounceTimeout) {
      clearTimeout(debounceTimeout);
    }

    try {
      cachedPages = await fetchAutocompletePages(query);
    } catch (e) {
      console.error("Error fetching autocomplete pages:", e);
      return null;
    }
  }

  if (!cachedPages || cachedPages.length === 0) {
    return null;
  }

  const currentPageId = window.getCurrentPage?.()?.external_id;

  const options = cachedPages
    .filter(page => page.external_id !== currentPageId)
    .map(page => {
      if (linkContext.type === "url") {
        return {
          label: page.title || "Untitled",
          detail: "internal link",
          apply: `/pages/${page.external_id}/`,
          type: "link",
        };
      } else {
        return {
          label: page.title || "Untitled",
          detail: "internal link",
          apply: (view, completion, from, to) => {
            const fullLink = `[${page.title}](/pages/${page.external_id}/)`;
            const linkStart = from - 1;
            view.dispatch({
              changes: { from: linkStart, to, insert: fullLink },
              selection: { anchor: linkStart + fullLink.length },
            });
          },
          type: "link",
        };
      }
    });

  return {
    from: linkContext.from,
    to: linkContext.to,
    options,
    filter: false,
  };
}

export const linkAutocomplete = autocompletion({
  override: [linkCompletionSource],
  activateOnTyping: true,
  maxRenderedOptions: 10,
  icons: false,
});
