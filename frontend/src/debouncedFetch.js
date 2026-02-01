/**
 * Creates a debounced fetch function for autocomplete sources.
 *
 * Returns an object with a `fetch` method that debounces API calls,
 * cancelling pending fetches when called with a new query.
 *
 * @param {number} delayMs - Debounce delay in milliseconds
 * @returns {{ fetch: (query: string, fetchFn: () => Promise<T>) => Promise<T> }}
 */
export function createDebouncedFetcher(delayMs = 150) {
  let debounceTimer = null;
  let cachedResult = null;
  let lastQuery = "";

  return {
    /**
     * Fetch data with debouncing. If the query matches the last query,
     * returns cached result. Otherwise, cancels any pending fetch and
     * starts a new debounced fetch.
     *
     * @param {string} query - The query string to use for cache key
     * @param {() => Promise<T>} fetchFn - The async function to call after debounce
     * @returns {Promise<T>} The fetched result
     */
    async fetch(query, fetchFn) {
      // Return cached result if query unchanged
      if (query === lastQuery && cachedResult !== null) {
        return cachedResult;
      }

      lastQuery = query;

      // Cancel any pending fetch
      if (debounceTimer) {
        clearTimeout(debounceTimer);
        debounceTimer = null;
      }

      // Create a debounced fetch
      const result = await new Promise((resolve, reject) => {
        debounceTimer = setTimeout(async () => {
          try {
            const data = await fetchFn();
            resolve(data);
          } catch (e) {
            reject(e);
          }
        }, delayMs);
      });

      cachedResult = result;
      return result;
    },

    /**
     * Clear the cache and any pending fetch.
     */
    reset() {
      if (debounceTimer) {
        clearTimeout(debounceTimer);
        debounceTimer = null;
      }
      cachedResult = null;
      lastQuery = "";
    },
  };
}
