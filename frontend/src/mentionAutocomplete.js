import { csrfFetch } from "./csrf.js";
import { createDebouncedFetcher } from "./debouncedFetch.js";
import { getCurrentOrgId } from "./lib/orgContext.js";

const API_BASE = "/api";

// `getCurrentOrgId` is imported from `lib/orgContext.js` (the plain-JS
// org-context module). Under the page-canonical invariant the page's
// org and the autocomplete-scope org are always the same — no need to
// derive the org from `cachedProjects` here.

/**
 * Find mention context when user is typing @...
 */
function findMentionContext(state, pos) {
  const line = state.doc.lineAt(pos);
  const textBefore = line.text.slice(0, pos - line.from);

  // Just typed @ at start or after whitespace
  const atMatch = textBefore.match(/(^|[\s])@([a-zA-Z0-9_]*)$/);
  if (atMatch) {
    const atIndex = textBefore.lastIndexOf("@");
    return {
      from: line.from + atIndex,
      to: pos,
      query: atMatch[2] || "",
    };
  }

  return null;
}

const fetcher = createDebouncedFetcher(150);
let lastOrgId = null;

async function fetchOrgMembers(orgId, query) {
  const response = await csrfFetch(
    `${API_BASE}/orgs/${orgId}/members/autocomplete/?q=${encodeURIComponent(query)}`
  );
  if (!response.ok) {
    throw new Error("Failed to fetch org members for autocomplete");
  }
  const data = await response.json();
  return data.members || [];
}

async function mentionCompletionSource(context) {
  console.log("[Mention] completionSource called, pos:", context.pos);
  const mentionContext = findMentionContext(context.state, context.pos);

  console.log("[Mention] context:", mentionContext);

  if (!mentionContext) {
    return null;
  }

  const orgId = getCurrentOrgId();
  console.log("[Mention] orgId:", orgId);
  if (!orgId) {
    return null;
  }

  const query = mentionContext.query;

  // Reset cache if org changed
  if (orgId !== lastOrgId) {
    fetcher.reset();
    lastOrgId = orgId;
  }

  let members;
  try {
    members = await fetcher.fetch(query, async () => {
      console.log("[Mention] Fetching members for org:", orgId, "query:", query);
      const result = await fetchOrgMembers(orgId, query);
      console.log("[Mention] Fetched members:", result);
      return result;
    });
  } catch (e) {
    console.error("[Mention] Error fetching org members:", e);
    return null;
  }

  if (!members || members.length === 0) {
    console.log("[Mention] No members found, returning null");
    return null;
  }

  const options = members.map((member) => ({
    label: member.username,
    apply: (view, completion, from, to) => {
      const mentionText = `@[${member.username}](@${member.external_id}) `;
      view.dispatch({
        changes: { from, to, insert: mentionText },
        selection: { anchor: from + mentionText.length },
      });
    },
    type: "mention",
  }));

  const result = {
    from: mentionContext.from,
    to: mentionContext.to,
    options,
    filter: false,
  };
  console.log("[Mention] Returning completion result:", result);
  return result;
}

// Export the completion source for combining with other sources
export { mentionCompletionSource };

// Test-only: clear module-level state so successive tests don't share the
// fetcher's debounce cache or the orgId-change tripwire.
export function __resetForTests() {
  fetcher.reset();
  lastOrgId = null;
}
