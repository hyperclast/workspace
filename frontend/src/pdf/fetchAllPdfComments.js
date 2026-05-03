/**
 * Page through the list-comments endpoint until every root comment has been
 * collected.
 *
 * The endpoint returns root comments in `items` (replies are nested under
 * each root via `replies`) plus a `count` total. We request successive
 * offsets in fixed-size batches and stop when either the latest batch is
 * shorter than `batchSize` or we have collected at least `count` items.
 * Concurrent inserts that grow `count` mid-pagination still terminate via
 * the short-batch check.
 *
 * @param {string} pageId
 * @param {(pageId: string, limit: number, offset: number) => Promise<{items: any[], count?: number}>} fetchFn
 * @param {object} [opts]
 * @param {number} [opts.batchSize=100]
 * @returns {Promise<any[]>}
 */
export async function fetchAllRootComments(pageId, fetchFn, opts = {}) {
  const batchSize = opts.batchSize ?? 100;
  const all = [];
  let offset = 0;
  // Hard cap to guarantee termination even if the server misbehaves.
  let safety = 1000;
  while (safety-- > 0) {
    const result = await fetchFn(pageId, batchSize, offset);
    const items = Array.isArray(result?.items) ? result.items : Array.isArray(result) ? result : [];
    all.push(...items);
    if (items.length < batchSize) break;
    if (typeof result?.count === "number" && all.length >= result.count) break;
    offset += batchSize;
  }
  return all;
}
