/**
 * Performance testing utilities
 *
 * Provides helpers for timing operations, logging results, and asserting thresholds
 * with support for default (fast) and full (thorough) modes.
 */

/**
 * Check if we're running in full performance test mode
 */
export const isFullMode = () => process.env.PERF_FULL === "1";

/**
 * Get configuration value based on mode
 * @param {number} defaultValue - Value for default/fast mode
 * @param {number} fullValue - Value for full/thorough mode
 * @returns {number}
 */
export const getConfig = (defaultValue, fullValue) => {
  return isFullMode() ? fullValue : defaultValue;
};

/**
 * Measure the execution time of a synchronous or async function
 * @param {Function} fn - Function to measure
 * @returns {Promise<{duration: number, result: any}>}
 */
export const measureTime = async (fn) => {
  const start = performance.now();
  const result = await fn();
  const duration = performance.now() - start;
  return { duration, result };
};

/**
 * Log performance results in a structured format
 * @param {string} testName - Name of the test
 * @param {number} duration - Duration in milliseconds
 * @param {number} threshold - Warning threshold in milliseconds
 * @param {Object} metadata - Additional metadata to log
 */
export const logPerf = (testName, duration, threshold, metadata = {}) => {
  const mode = isFullMode() ? "FULL" : "DEFAULT";
  const status = duration > threshold * 2 ? "⚠️  SLOW" : duration > threshold ? "⚠️  WARN" : "✓";

  console.log(`[PERF] ${status} ${testName}`);
  console.log(`  Duration: ${duration.toFixed(2)}ms`);
  console.log(`  Threshold: ${threshold}ms (${mode} mode)`);

  if (Object.keys(metadata).length > 0) {
    console.log(`  Metadata:`, metadata);
  }
};

/**
 * Assert that a duration is within acceptable bounds
 * @param {number} duration - Measured duration in milliseconds
 * @param {number} threshold - Target threshold in milliseconds
 * @param {string} message - Error message if assertion fails
 * @throws {Error} If duration exceeds 3x threshold
 */
export const assertPerf = (duration, threshold, message) => {
  const failThreshold = threshold * 3; // Fail only if 3x slower

  if (duration > threshold * 2) {
    console.warn(
      `⚠️  PERF WARNING: ${message} - ${duration.toFixed(2)}ms (threshold: ${threshold}ms)`
    );
  }

  if (duration > failThreshold) {
    throw new Error(
      `Performance assertion failed: ${message}\n` +
        `Duration: ${duration.toFixed(2)}ms\n` +
        `Threshold: ${threshold}ms\n` +
        `Fail threshold: ${failThreshold}ms (3x)`
    );
  }
};

/**
 * Run a performance test with automatic timing, logging, and assertion
 * @param {string} testName - Name of the test
 * @param {Function} fn - Test function to run
 * @param {number} threshold - Target threshold in milliseconds
 * @param {Object} options - Additional options
 * @param {Object} options.metadata - Additional metadata to log
 * @param {boolean} options.skipAssert - Skip assertion (only log)
 * @returns {Promise<{duration: number, result: any}>}
 */
export const runPerfTest = async (testName, fn, threshold, options = {}) => {
  const { metadata = {}, skipAssert = false } = options;

  const { duration, result } = await measureTime(fn);

  logPerf(testName, duration, threshold, metadata);

  if (!skipAssert) {
    assertPerf(duration, threshold, testName);
  }

  return { duration, result };
};

/**
 * Measure the size of data in bytes
 * @param {Uint8Array|ArrayBuffer|string} data - Data to measure
 * @returns {number} Size in bytes
 */
export const measureSize = (data) => {
  if (data instanceof Uint8Array) {
    return data.length;
  }
  if (data instanceof ArrayBuffer) {
    return data.byteLength;
  }
  if (typeof data === "string") {
    return new TextEncoder().encode(data).length;
  }
  return 0;
};

/**
 * Format bytes to human-readable string
 * @param {number} bytes - Number of bytes
 * @returns {string}
 */
export const formatBytes = (bytes) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

/**
 * Calculate percentage overhead
 * @param {number} withOverhead - Duration with overhead
 * @param {number} baseline - Baseline duration
 * @returns {number} Overhead percentage
 */
export const calculateOverhead = (withOverhead, baseline) => {
  if (baseline === 0) return 0;
  return ((withOverhead - baseline) / baseline) * 100;
};
