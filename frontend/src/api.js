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
 * @param {boolean} orgMembersCanAccess - If true, all org members can access; if false, only project editors
 * @returns {Promise<Object>} The created project object
 */
export async function createProject(orgId, name, description = "", orgMembersCanAccess = true) {
  const response = await csrfFetch(`${API_BASE}/projects/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      org_id: orgId,
      name,
      description,
      org_members_can_access: orgMembersCanAccess,
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
 * @param {string} [copyFrom] - Optional external ID of a page to copy content from
 * @returns {Promise<Object>} The created page object
 */
export async function createPage(projectId, title, copyFrom = null) {
  const body = { project_id: projectId, title };
  if (copyFrom) {
    body.copy_from = copyFrom;
  }
  const response = await csrfFetch(`${API_BASE}/pages/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
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
 * Trigger immediate link sync with the provided content.
 * @param {string} externalId - External ID of the page
 * @param {string} content - Current editor content to sync links from
 * @returns {Promise<{synced: boolean, outgoing: Array, incoming: Array}>}
 */
export async function syncPageLinks(externalId, content = null) {
  const response = await csrfFetch(`${API_BASE}/pages/${externalId}/links/sync/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!response.ok) {
    throw new Error(`Failed to sync page links: ${response.statusText}`);
  }
  return response.json();
}

// AI Indexing API

/**
 * Fetch the indexing status for the current user's pages.
 * @returns {Promise<{total_pages: number, indexed_pages: number, pending_pages: number, has_valid_provider: boolean}>}
 */
export async function fetchIndexingStatus() {
  const response = await csrfFetch(`${API_BASE}/ai/indexing/status/`);
  if (!response.ok) {
    throw new Error(`Failed to fetch indexing status: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Trigger indexing of all unindexed pages.
 * @returns {Promise<{triggered: boolean, pages_queued: number, message: string}>}
 */
export async function triggerIndexing() {
  const response = await csrfFetch(`${API_BASE}/ai/indexing/trigger/`, {
    method: "POST",
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.message || `Failed to trigger indexing: ${response.statusText}`);
  }
  return response.json();
}

// Access Code API (View-Only Links)

/**
 * Generate or retrieve an access code for a view-only link.
 * @param {string} pageExternalId - External ID of the page
 * @returns {Promise<{access_code: string}>}
 */
export async function generateAccessCode(pageExternalId) {
  const response = await csrfFetch(`${API_BASE}/pages/${pageExternalId}/access-code/`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Failed to generate access code: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Remove the view-only link access code from a page.
 * @param {string} pageExternalId - External ID of the page
 * @returns {Promise<void>}
 */
export async function removeAccessCode(pageExternalId) {
  const response = await csrfFetch(`${API_BASE}/pages/${pageExternalId}/access-code/`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(`Failed to remove access code: ${response.statusText}`);
  }
}

// Page Editor API

/**
 * Fetch page sharing settings.
 * @param {string} pageExternalId - External ID of the page
 * @returns {Promise<{your_access: string, access_code: string|null, can_manage_sharing: boolean}>}
 */
export async function fetchPageSharing(pageExternalId) {
  const response = await csrfFetch(`${API_BASE}/pages/${pageExternalId}/sharing/`);
  if (!response.ok) {
    throw new Error(`Failed to fetch page sharing: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Fetch page editors.
 * @param {string} pageExternalId - External ID of the page
 * @returns {Promise<Array>} Array of page editors
 */
export async function fetchPageEditors(pageExternalId) {
  const response = await csrfFetch(`${API_BASE}/pages/${pageExternalId}/editors/`);
  if (!response.ok) {
    throw new Error(`Failed to fetch page editors: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Add a page editor by email.
 * @param {string} pageExternalId - External ID of the page
 * @param {string} email - Email of the user to add
 * @param {string} role - Role to assign ("viewer" or "editor")
 * @returns {Promise<Object>} The added editor object
 */
export async function addPageEditor(pageExternalId, email, role = "viewer") {
  const response = await csrfFetch(`${API_BASE}/pages/${pageExternalId}/editors/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, role }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.message || `Failed to add page editor: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Remove a page editor.
 * @param {string} pageExternalId - External ID of the page
 * @param {string} editorExternalId - External ID of the editor to remove
 * @returns {Promise<void>}
 */
export async function removePageEditor(pageExternalId, editorExternalId) {
  const response = await csrfFetch(
    `${API_BASE}/pages/${pageExternalId}/editors/${editorExternalId}/`,
    {
      method: "DELETE",
    }
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.message || `Failed to remove page editor: ${response.statusText}`);
  }
}

/**
 * Update a page editor's role.
 * @param {string} pageExternalId - External ID of the page
 * @param {string} editorExternalId - External ID of the editor to update
 * @param {string} role - New role ("viewer" or "editor")
 * @returns {Promise<Object>} The updated editor object
 */
export async function updatePageEditorRole(pageExternalId, editorExternalId, role) {
  const response = await csrfFetch(
    `${API_BASE}/pages/${pageExternalId}/editors/${editorExternalId}/`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    }
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.message || `Failed to update page editor role: ${response.statusText}`);
  }
  return response.json();
}

// Files API

/**
 * Create a file upload and get a signed URL for uploading.
 * @param {string} projectId - External ID of the project
 * @param {string} filename - Original filename
 * @param {string} contentType - MIME type of the file
 * @param {number} sizeBytes - File size in bytes
 * @returns {Promise<{file: Object, upload_url: string, upload_headers: Object, expires_at: string, webhook_enabled: boolean}>}
 */
export async function createFileUpload(projectId, filename, contentType, sizeBytes) {
  const response = await csrfFetch(`${API_BASE}/files/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      project_id: projectId,
      filename,
      content_type: contentType,
      size_bytes: sizeBytes,
    }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.message || `Failed to create file upload: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Upload a file directly to the storage backend using a signed URL.
 * @param {string} uploadUrl - Signed URL for uploading
 * @param {File} file - File object to upload
 * @param {Object} headers - Headers to include in the upload request
 * @returns {Promise<Response>}
 */
export async function uploadFileToStorage(uploadUrl, file, headers) {
  const response = await fetch(uploadUrl, {
    method: "PUT",
    headers,
    body: file,
  });
  if (!response.ok) {
    throw new Error(`Failed to upload file to storage: ${response.statusText}`);
  }
  return response;
}

/**
 * Finalize a file upload after uploading to storage.
 * Only needed when webhook_enabled is false.
 * @param {string} fileId - External ID of the file upload
 * @param {string} [etag] - Optional ETag from storage upload response
 * @returns {Promise<Object>} The finalized file upload object
 */
export async function finalizeFileUpload(fileId, etag = null) {
  const body = etag ? { etag } : {};
  const response = await csrfFetch(`${API_BASE}/files/${fileId}/finalize/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.message || `Failed to finalize file upload: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Mark a file upload as failed (for error recovery).
 * @param {string} fileId - External ID of the file upload
 * @returns {Promise<Object>} The updated file upload object
 */
export async function markUploadFailed(fileId) {
  const response = await csrfFetch(`${API_BASE}/files/${fileId}/finalize/?mark_failed=true`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.message || `Failed to mark upload as failed: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Fetch files for a project.
 * @param {string} projectId - External ID of the project
 * @param {string} [status] - Optional status filter ('pending', 'ready', 'failed')
 * @returns {Promise<{items: Array, total: number, page: number, page_size: number}>}
 */
export async function fetchProjectFiles(projectId, status = "ready") {
  const url = status
    ? `${API_BASE}/files/projects/${projectId}/?status=${status}`
    : `${API_BASE}/files/projects/${projectId}/`;
  const response = await csrfFetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch project files: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Upload a file to a project (complete flow).
 * Creates the upload, uploads to storage, and finalizes (if webhook not enabled).
 * @param {string} projectId - External ID of the project
 * @param {File} file - File object to upload
 * @param {Function} [onProgress] - Optional progress callback (not implemented yet)
 * @returns {Promise<Object>} The file upload object
 */
export async function uploadFile(projectId, file, onProgress = null) {
  // Step 1: Create the upload and get signed URL
  const createResult = await createFileUpload(projectId, file.name, file.type, file.size);

  try {
    // Step 2: Upload file to storage using signed URL
    await uploadFileToStorage(createResult.upload_url, file, createResult.upload_headers);
  } catch (error) {
    // Upload failed - mark the upload as failed for cleanup
    try {
      await markUploadFailed(createResult.file.external_id);
    } catch (markError) {
      console.error("Failed to mark upload as failed:", markError);
    }
    throw error;
  }

  // Step 3: Finalize based on webhook status
  if (createResult.webhook_enabled) {
    // Webhook will handle finalization automatically
    // Return the pending file object - caller should poll for status if needed
    return createResult.file;
  } else {
    // Webhook not enabled - finalize manually
    const finalizedFile = await finalizeFileUpload(createResult.file.external_id);
    return finalizedFile;
  }
}
