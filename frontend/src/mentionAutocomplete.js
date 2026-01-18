import { csrfFetch } from "./csrf.js";

const API_BASE = "/api";

/**
 * Get the current org ID from cached projects.
 * Uses the first project's org since user can only @mention within their org context.
 */
function getCurrentOrgId() {
  const projects = window._cachedProjects;
  if (!projects || projects.length === 0) return null;
  return projects[0]?.org?.external_id || null;
}

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

let cachedMembers = null;
let lastQuery = "";
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

  // Fetch members if query or org changed
  if (query !== lastQuery || orgId !== lastOrgId || !cachedMembers) {
    lastQuery = query;
    lastOrgId = orgId;

    try {
      console.log("[Mention] Fetching members for org:", orgId, "query:", query);
      cachedMembers = await fetchOrgMembers(orgId, query);
      console.log("[Mention] Fetched members:", cachedMembers);
    } catch (e) {
      console.error("[Mention] Error fetching org members:", e);
      return null;
    }
  }

  if (!cachedMembers || cachedMembers.length === 0) {
    console.log("[Mention] No members found, returning null");
    return null;
  }

  const options = cachedMembers.map((member) => ({
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
