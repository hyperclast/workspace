/**
 * API service module for Hyperclast.
 * Centralizes all API calls for projects, orgs, and pages.
 */

import { csrfFetch } from "./csrf.js";

const API_BASE = "/api";

// Projects API

/**
 * Fetch all projects with their pages.
 * @returns {Promise<Array>} Array of projects with nested pages
 */
export async function fetchProjectsWithPages() {
  const response = await csrfFetch(`${API_BASE}/projects/?details=full`);
  if (!response.ok) {
    throw new Error(`Failed to fetch projects: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Create a new project in an organization.
 * @param {string} orgId - External ID of the organization
 * @param {string} name - Name of the project
 * @param {string} description - Optional project description
 * @returns {Promise<Object>} The created project object
 */
export async function createProject(orgId, name, description = "") {
  const response = await csrfFetch(`${API_BASE}/projects/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      org_id: orgId,
      name,
      description,
    }),
  });
  if (!response.ok) {
    throw new Error(`Failed to create project: ${response.statusText}`);
  }
  return response.json();
}

// Organizations API

/**
 * Fetch all organizations the user is a member of.
 * @returns {Promise<Array>} Array of organizations
 */
export async function fetchOrgs() {
  const response = await csrfFetch(`${API_BASE}/orgs/`);
  if (!response.ok) {
    throw new Error(`Failed to fetch organizations: ${response.statusText}`);
  }
  return response.json();
}

// Pages API

/**
 * Create a new page in a project.
 * @param {string} projectId - External ID of the project
 * @param {string} title - Title of the page
 * @returns {Promise<Object>} The created page object
 */
export async function createPage(projectId, title) {
  const response = await csrfFetch(`${API_BASE}/pages/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      project_id: projectId,
      title,
    }),
  });
  if (!response.ok) {
    throw new Error(`Failed to create page: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Fetch a specific page by its external ID.
 * @param {string} externalId - External ID of the page
 * @returns {Promise<Object>} The page object
 */
export async function fetchPage(externalId) {
  const response = await csrfFetch(`${API_BASE}/pages/${externalId}/`);
  if (!response.ok) {
    throw new Error(`Failed to fetch page: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Delete a page by its external ID.
 * @param {string} externalId - External ID of the page to delete
 * @returns {Promise<void>}
 */
export async function deletePage(externalId) {
  const response = await csrfFetch(`${API_BASE}/pages/${externalId}/`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(`Failed to delete page: ${response.statusText}`);
  }
}

/**
 * Fetch outgoing and incoming links for a page.
 * @param {string} externalId - External ID of the page
 * @returns {Promise<{outgoing: Array, incoming: Array}>}
 */
export async function fetchPageLinks(externalId) {
  const response = await csrfFetch(`${API_BASE}/pages/${externalId}/links/`);
  if (!response.ok) {
    throw new Error(`Failed to fetch page links: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Trigger immediate link sync for a page.
 * @param {string} externalId - External ID of the page
 * @param {string} contentHash - Optional content hash to skip if unchanged
 * @returns {Promise<{synced: boolean, outgoing: Array, incoming: Array}>}
 */
export async function syncPageLinks(externalId, contentHash = null) {
  const response = await csrfFetch(`${API_BASE}/pages/${externalId}/links/sync/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content_hash: contentHash }),
  });
  if (!response.ok) {
    throw new Error(`Failed to sync page links: ${response.statusText}`);
  }
  return response.json();
}
