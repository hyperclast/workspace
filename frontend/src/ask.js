/**
 * Ask API Client
 *
 * Provides functions to interact with the ask API endpoint.
 */

import { API_BASE_URL } from "./config.js";
import { csrfFetch } from "./csrf.js";

/**
 * Custom error class for Ask API errors
 */
export class AskError extends Error {
  constructor(code, message, status) {
    super(message);
    this.name = "AskError";
    this.code = code;
    this.status = status;
  }
}

/**
 * Ask a question with optional page context
 *
 * @param {string} query - The question to ask
 * @param {string[]} pageIds - Optional array of page IDs to provide as context
 * @returns {Promise<Object>} Response with answer and page citations
 * @throws {AskError} If the API request fails
 */
export async function askQuestion(query, pageIds = []) {
  const response = await csrfFetch(`${API_BASE_URL}/api/ask/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include", // Include session cookie
    body: JSON.stringify({
      query: query,
      page_ids: pageIds,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new AskError(errorData.error, errorData.message, response.status);
  }

  return response.json();
}

/**
 * Search pages by title for autocomplete
 *
 * @param {string} searchQuery - The search term
 * @returns {Promise<Object>} Response with array of matching pages
 * @throws {Error} If the API request fails
 */
export async function autocompletePages(searchQuery) {
  const params = new URLSearchParams();
  if (searchQuery) {
    params.append("q", searchQuery);
  }

  const response = await csrfFetch(`${API_BASE_URL}/api/pages/autocomplete/?${params.toString()}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error("Failed to fetch autocomplete suggestions");
  }

  return response.json();
}
