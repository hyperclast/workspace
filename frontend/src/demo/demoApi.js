/**
 * Demo API - mock implementations that return demo data
 *
 * These functions match the signatures in api.js but return local demo data
 * instead of making network requests.
 */

import { DEMO_PROJECTS, DEMO_PAGES, getDemoPage } from "./demoContent.js";
import { DemoModeError, getDemoFiletype } from "./index.js";

/**
 * Fetch projects with pages - returns demo project structure
 */
export async function fetchProjectsWithPages() {
  // Small delay to feel realistic
  await new Promise((resolve) => setTimeout(resolve, 50));
  return DEMO_PROJECTS;
}

/**
 * Fetch a single page by external_id
 */
export async function fetchPage(externalId) {
  await new Promise((resolve) => setTimeout(resolve, 30));
  const page = getDemoPage(externalId);
  if (!page) {
    throw new Error(`Demo page not found: ${externalId}`);
  }

  // Check for filetype override (from Change Page Type in demo mode)
  const filetypeOverride = getDemoFiletype(externalId);
  if (filetypeOverride) {
    return {
      ...page,
      filetype: filetypeOverride,
      details: {
        ...page.details,
        filetype: filetypeOverride,
      },
    };
  }

  return page;
}

/**
 * Create page - not available in demo mode
 */
export async function createPage(_projectId, _title, _copyFrom) {
  throw new DemoModeError("create pages");
}

/**
 * Delete page - not available in demo mode
 */
export async function deletePage(_externalId) {
  throw new DemoModeError("delete pages");
}

/**
 * Update page - silently succeeds (changes are local-only)
 * This allows title editing to "work" in the UI even though it's not persisted
 */
export async function updatePage(externalId, _data) {
  await new Promise((resolve) => setTimeout(resolve, 30));
  return getDemoPage(externalId);
}

/**
 * Create project - not available in demo mode
 */
export async function createProject(_orgId, _name, _description) {
  throw new DemoModeError("create projects");
}

/**
 * Delete project - not available in demo mode
 */
export async function deleteProject(_externalId) {
  throw new DemoModeError("delete projects");
}

/**
 * Fetch orgs - returns demo org
 */
export async function fetchOrgs() {
  await new Promise((resolve) => setTimeout(resolve, 30));
  return [
    {
      external_id: "demo-org",
      name: "Demo Organization",
      role: "admin",
    },
  ];
}

/**
 * Generate access code - not available in demo mode
 */
export async function generateAccessCode(_externalId) {
  throw new DemoModeError("generate share links");
}

/**
 * Autocomplete pages - search demo pages by title
 */
export async function autocompletePages(query) {
  await new Promise((resolve) => setTimeout(resolve, 30));
  const q = query.toLowerCase();
  const results = [];

  for (const project of DEMO_PROJECTS) {
    for (const page of project.pages) {
      if (page.title.toLowerCase().includes(q)) {
        results.push({
          external_id: page.external_id,
          title: page.title,
          project_name: project.name,
        });
      }
    }
  }

  return results;
}

/**
 * Internal link regex for extracting page links from content
 */
const INTERNAL_LINK_REGEX = /\[([^\]]+)\]\(\/pages\/([a-zA-Z0-9-]+)\/?[^)]*\)/g;

/**
 * Extract internal links from content
 */
function extractLinksFromContent(content, sourcePageId) {
  const links = [];
  const regex = new RegExp(INTERNAL_LINK_REGEX.source, "g");
  let match;
  while ((match = regex.exec(content)) !== null) {
    const linkText = match[1];
    const targetPageId = match[2];
    if (targetPageId !== sourcePageId) {
      links.push({
        external_id: targetPageId,
        link_text: linkText,
      });
    }
  }
  return links;
}

/**
 * Fetch page links - returns outgoing and incoming (backlinks) for a demo page
 */
export async function fetchPageLinks(pageId) {
  await new Promise((resolve) => setTimeout(resolve, 30));

  const currentPage = getDemoPage(pageId);
  if (!currentPage) {
    return { outgoing: [], incoming: [] };
  }

  // Get outgoing links from current page
  const content = currentPage.details?.content || "";
  const outgoingRaw = extractLinksFromContent(content, pageId);

  // Resolve titles for outgoing links
  const outgoing = outgoingRaw.map((link) => {
    const targetPage = getDemoPage(link.external_id);
    return {
      external_id: link.external_id,
      title: targetPage?.title || link.link_text,
      link_text: link.link_text,
    };
  });

  // Find backlinks - scan all demo pages for links TO this page
  const incoming = [];
  for (const [sourceId, sourcePage] of Object.entries(DEMO_PAGES)) {
    if (sourceId === pageId) continue;
    const sourceContent = sourcePage.details?.content || "";
    const linksInSource = extractLinksFromContent(sourceContent, sourceId);
    for (const link of linksInSource) {
      if (link.external_id === pageId) {
        incoming.push({
          external_id: sourceId,
          title: sourcePage.title,
          link_text: link.link_text,
        });
      }
    }
  }

  return { outgoing, incoming };
}

/**
 * Sync page links - in demo mode, just return current state (no-op)
 */
export async function syncPageLinks(pageId, _content) {
  // In demo mode, syncing is a no-op - just return current links
  const { outgoing, incoming } = await fetchPageLinks(pageId);
  return { synced: true, outgoing, incoming };
}
