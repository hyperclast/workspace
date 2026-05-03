import { describe, test, expect, vi } from "vitest";
import { fetchAllRootComments } from "../../pdf/fetchAllPdfComments.js";

function makeBatches(allItems, batchSize) {
  return (pageId, limit, offset) => {
    const slice = allItems.slice(offset, offset + limit);
    return Promise.resolve({ items: slice, count: allItems.length });
  };
}

describe("fetchAllRootComments", () => {
  test("returns the single page when count fits in one batch", async () => {
    const items = Array.from({ length: 7 }, (_, i) => ({ id: i }));
    const fetchFn = vi.fn(makeBatches(items, 100));

    const result = await fetchAllRootComments("p1", fetchFn);

    expect(result).toEqual(items);
    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(fetchFn).toHaveBeenCalledWith("p1", 100, 0);
  });

  test("pages through until all root comments are collected (50 items)", async () => {
    // Mirrors the plan's test scenario: 50 root comments on a PDF page.
    const items = Array.from({ length: 50 }, (_, i) => ({
      external_id: `c${i}`,
      pdf_anchor: { page: 1, rects: [], text: `t${i}` },
    }));
    const fetchFn = vi.fn(makeBatches(items, 20));

    const result = await fetchAllRootComments("p1", fetchFn, { batchSize: 20 });

    expect(result).toHaveLength(50);
    expect(result.map((c) => c.external_id)).toEqual(items.map((c) => c.external_id));
    expect(fetchFn).toHaveBeenCalledTimes(3);
    expect(fetchFn).toHaveBeenNthCalledWith(1, "p1", 20, 0);
    expect(fetchFn).toHaveBeenNthCalledWith(2, "p1", 20, 20);
    expect(fetchFn).toHaveBeenNthCalledWith(3, "p1", 20, 40);
  });

  test("stops when the returned batch is shorter than batchSize", async () => {
    const items = Array.from({ length: 25 }, (_, i) => ({ id: i }));
    const fetchFn = vi.fn(makeBatches(items, 10));

    const result = await fetchAllRootComments("p1", fetchFn, { batchSize: 10 });

    expect(result).toHaveLength(25);
    expect(fetchFn).toHaveBeenCalledTimes(3);
  });

  test("stops once all.length >= count even if a full batch was returned", async () => {
    // Server reports count=20 but happens to return exactly 20 in one batch.
    const items = Array.from({ length: 20 }, (_, i) => ({ id: i }));
    const fetchFn = vi.fn().mockResolvedValueOnce({ items, count: 20 });

    const result = await fetchAllRootComments("p1", fetchFn, { batchSize: 20 });

    expect(result).toHaveLength(20);
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  test("returns [] for an empty page", async () => {
    const fetchFn = vi.fn().mockResolvedValueOnce({ items: [], count: 0 });

    const result = await fetchAllRootComments("p1", fetchFn);

    expect(result).toEqual([]);
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  test("tolerates a bare-array response shape", async () => {
    const items = [{ id: 1 }, { id: 2 }];
    const fetchFn = vi.fn().mockResolvedValueOnce(items);

    const result = await fetchAllRootComments("p1", fetchFn);

    expect(result).toEqual(items);
  });

  test("propagates fetch errors", async () => {
    const fetchFn = vi.fn().mockRejectedValueOnce(new Error("boom"));

    await expect(fetchAllRootComments("p1", fetchFn)).rejects.toThrow("boom");
  });
});
