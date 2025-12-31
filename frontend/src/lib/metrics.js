/**
 * Metrics and Observability Module
 *
 * Provides structured logging and timing metrics for page load, collaboration,
 * and other critical paths. Designed to support future extension into a full
 * observability platform with remote telemetry.
 *
 * Usage:
 *   import { metrics } from './lib/metrics.js';
 *
 *   // Start a timed operation
 *   const span = metrics.startSpan('page_load', { pageId: 'abc123' });
 *   // ... do work ...
 *   span.end({ status: 'success', contentLength: 1234 });
 *
 *   // Record an event
 *   metrics.event('collab_sync_complete', { pageId: 'abc123', duration: 150 });
 *
 *   // Get metrics summary
 *   const summary = metrics.getSummary();
 */

// Configuration
const CONFIG = {
  enabled: true,
  consoleOutput: true,
  bufferSize: 1000, // Keep last N events in memory
  samplingRate: 1.0, // 1.0 = log everything, 0.1 = 10% sampling
  slowThresholds: {
    page_load: 500, // ms - page load should be under 500ms
    rest_fetch: 200, // ms - REST API call should be under 200ms
    ws_connect: 1000, // ms - WebSocket connection should be under 1s
    ws_sync: 2000, // ms - WebSocket sync should be under 2s
    editor_init: 100, // ms - Editor initialization should be under 100ms
    editor_upgrade: 50, // ms - Editor upgrade should be under 50ms
  },
};

// Event buffer for in-memory storage
const eventBuffer = [];
const spanBuffer = [];

// Active spans (for nested timing)
const activeSpans = new Map();

// Session info
const sessionId = crypto.randomUUID();
const sessionStartTime = performance.now();

/**
 * Format timestamp for logging
 */
function formatTime(timestamp) {
  return new Date(timestamp).toISOString();
}

/**
 * Get relative time since session start
 */
function getRelativeTime() {
  return Math.round(performance.now() - sessionStartTime);
}

/**
 * Determine if we should sample this event
 */
function shouldSample() {
  return Math.random() < CONFIG.samplingRate;
}

/**
 * Core logging function
 */
function logToConsole(level, category, message, data) {
  if (!CONFIG.consoleOutput) return;

  const prefix = `[${getRelativeTime()}ms] [${category}]`;
  const style =
    {
      info: "color: #4a9eff",
      warn: "color: #ffb347",
      error: "color: #ff6b6b",
      perf: "color: #77dd77",
      slow: "color: #ff6b6b; font-weight: bold",
    }[level] || "";

  if (data && Object.keys(data).length > 0) {
    console.log(`%c${prefix} ${message}`, style, data);
  } else {
    console.log(`%c${prefix} ${message}`, style);
  }
}

/**
 * Create a span for timing an operation
 */
function startSpan(name, attributes = {}) {
  const spanId = crypto.randomUUID().slice(0, 8);
  const startTime = performance.now();
  const startTimestamp = Date.now();

  const span = {
    spanId,
    name,
    attributes,
    startTime,
    startTimestamp,
    events: [],
    ended: false,
  };

  activeSpans.set(spanId, span);

  if (CONFIG.consoleOutput) {
    logToConsole("info", name, `▶ Started`, attributes);
  }

  return {
    spanId,

    // Add an event within this span
    addEvent(eventName, eventAttributes = {}) {
      const relativeTime = performance.now() - startTime;
      span.events.push({
        name: eventName,
        timestamp: Date.now(),
        relativeTime: Math.round(relativeTime),
        attributes: eventAttributes,
      });

      if (CONFIG.consoleOutput) {
        logToConsole(
          "info",
          name,
          `  ├─ ${eventName} (+${Math.round(relativeTime)}ms)`,
          eventAttributes
        );
      }
    },

    // Set additional attributes
    setAttributes(attrs) {
      Object.assign(span.attributes, attrs);
    },

    // End the span
    end(endAttributes = {}) {
      if (span.ended) {
        console.warn(`Span ${name} (${spanId}) already ended`);
        return;
      }

      span.ended = true;
      const duration = Math.round(performance.now() - startTime);

      const record = {
        ...span,
        endTime: performance.now(),
        endTimestamp: Date.now(),
        duration,
        endAttributes,
        sessionId,
      };

      // Check if this was slow
      const threshold = CONFIG.slowThresholds[name];
      const isSlow = threshold && duration > threshold;

      if (CONFIG.consoleOutput) {
        const status = endAttributes.status || "complete";
        const level = isSlow ? "slow" : status === "error" ? "error" : "perf";
        const slowWarning = isSlow ? ` ⚠️ SLOW (threshold: ${threshold}ms)` : "";
        logToConsole(level, name, `◀ Completed in ${duration}ms${slowWarning}`, {
          ...endAttributes,
          duration,
          eventCount: span.events.length,
        });
      }

      // Store in buffer
      spanBuffer.push(record);
      if (spanBuffer.length > CONFIG.bufferSize) {
        spanBuffer.shift();
      }

      activeSpans.delete(spanId);

      return record;
    },
  };
}

/**
 * Record a point-in-time event
 */
function event(name, attributes = {}) {
  if (!CONFIG.enabled || !shouldSample()) return;

  const record = {
    type: "event",
    name,
    timestamp: Date.now(),
    relativeTime: getRelativeTime(),
    attributes,
    sessionId,
  };

  eventBuffer.push(record);
  if (eventBuffer.length > CONFIG.bufferSize) {
    eventBuffer.shift();
  }

  if (CONFIG.consoleOutput) {
    logToConsole("info", "EVENT", name, attributes);
  }

  return record;
}

/**
 * Record an error
 */
function error(name, err, attributes = {}) {
  const record = event(name, {
    ...attributes,
    error: err.message,
    stack: err.stack?.split("\n").slice(0, 3).join("\n"),
  });

  if (CONFIG.consoleOutput) {
    logToConsole("error", "ERROR", name, { error: err.message, ...attributes });
  }

  return record;
}

/**
 * Get summary statistics
 */
function getSummary() {
  const now = Date.now();
  const recentSpans = spanBuffer.filter((s) => now - s.endTimestamp < 60000); // Last minute

  // Group spans by name
  const byName = {};
  for (const span of recentSpans) {
    if (!byName[span.name]) {
      byName[span.name] = [];
    }
    byName[span.name].push(span);
  }

  // Calculate stats for each span type
  const stats = {};
  for (const [name, spans] of Object.entries(byName)) {
    const durations = spans.map((s) => s.duration);
    const sorted = [...durations].sort((a, b) => a - b);

    stats[name] = {
      count: spans.length,
      min: Math.min(...durations),
      max: Math.max(...durations),
      avg: Math.round(durations.reduce((a, b) => a + b, 0) / durations.length),
      p50: sorted[Math.floor(sorted.length * 0.5)],
      p95: sorted[Math.floor(sorted.length * 0.95)],
      p99: sorted[Math.floor(sorted.length * 0.99)],
      threshold: CONFIG.slowThresholds[name] || null,
      slowCount: spans.filter((s) => {
        const threshold = CONFIG.slowThresholds[name];
        return threshold && s.duration > threshold;
      }).length,
    };
  }

  return {
    sessionId,
    sessionDuration: getRelativeTime(),
    spanCount: spanBuffer.length,
    eventCount: eventBuffer.length,
    stats,
  };
}

/**
 * Get raw event and span buffers (for debugging/export)
 */
function getRawData() {
  return {
    spans: [...spanBuffer],
    events: [...eventBuffer],
    activeSpans: Array.from(activeSpans.values()),
  };
}

/**
 * Clear buffers
 */
function clear() {
  eventBuffer.length = 0;
  spanBuffer.length = 0;
  activeSpans.clear();
}

/**
 * Update configuration
 */
function configure(options) {
  Object.assign(CONFIG, options);
}

// Export the metrics API
export const metrics = {
  startSpan,
  event,
  error,
  getSummary,
  getRawData,
  clear,
  configure,

  // Expose config for testing
  get config() {
    return { ...CONFIG };
  },

  // Expose session info
  get sessionId() {
    return sessionId;
  },
};

// Make available globally for debugging in console
if (typeof window !== "undefined") {
  window.__metrics = metrics;
}

export default metrics;
