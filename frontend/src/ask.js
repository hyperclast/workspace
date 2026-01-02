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
 * @param {Object} options - Optional parameters
 * @param {string} options.provider - Provider to use (openai, anthropic, google, custom)
 * @param {string} options.configId - Specific config ID to use
 * @param {string} options.model - Model ID to use
 * @returns {Promise<Object>} Response with answer and page citations
 * @throws {AskError} If the API request fails
 */
export async function askQuestion(query, pageIds = [], options = {}) {
  const body = {
    query: query,
    page_ids: pageIds,
  };

  if (options.provider) {
    body.provider = options.provider;
  }
  if (options.configId) {
    body.config_id = options.configId;
  }
  if (options.model) {
    body.model = options.model;
  }

  const response = await csrfFetch(`${API_BASE_URL}/api/ask/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new AskError(errorData.error, errorData.message, response.status);
  }

  return response.json();
}

/**
 * Fetch available AI providers for the current user
 *
 * @returns {Promise<Array>} Array of available provider configs
 */
export async function fetchAvailableProviders() {
  const response = await fetch(`${API_BASE_URL}/api/ai/providers/available/`, {
    credentials: "include",
  });

  if (!response.ok) {
    return [];
  }

  return response.json();
}

/**
 * Fetch available models for a specific provider
 *
 * @param {string} provider - Provider ID (openai, anthropic, google, custom)
 * @returns {Promise<Object>} Object with models array and default_model
 */
export async function fetchProviderModels(provider) {
  const response = await fetch(`${API_BASE_URL}/api/ai/models/${provider}/`, {
    credentials: "include",
  });

  if (!response.ok) {
    return { provider, models: [], default_model: null };
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
