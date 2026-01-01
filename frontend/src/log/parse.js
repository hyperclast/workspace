/**
 * Apache/Nginx Combined Log Format Parser
 *
 * Format: IP - - [timestamp] "METHOD path HTTP/x.x" status bytes "referer" "user-agent"
 * Example: 192.168.1.1 - - [10/Oct/2000:13:55:36 -0700] "GET /index.html HTTP/1.1" 200 2326 "-" "Mozilla/5.0"
 */

// Regex for Apache/Nginx combined log format
const LOG_REGEX =
  /^(\S+)\s+\S+\s+\S+\s+\[([^\]]+)\]\s+"([A-Z]+)\s+(\S+)\s+HTTP\/[\d.]+"\s+(\d{3})\s+(\d+|-)\s+"([^"]*)"\s+"([^"]*)"$/;

// Simpler regex for common log format (without referer/user-agent)
const COMMON_LOG_REGEX =
  /^(\S+)\s+\S+\s+\S+\s+\[([^\]]+)\]\s+"([A-Z]+)\s+(\S+)\s+HTTP\/[\d.]+"\s+(\d{3})\s+(\d+|-)$/;

// IP address regex for highlighting
const IP_REGEX = /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/;

/**
 * Parse a single log line
 * @param {string} line - Raw log line
 * @param {number} lineNumber - Line number (1-indexed)
 * @returns {Object|null} Parsed log entry or null if unparseable
 */
export function parseLogLine(line, lineNumber) {
  if (!line || line.trim() === "") {
    return null;
  }

  // Try combined format first
  let match = line.match(LOG_REGEX);
  if (match) {
    return {
      lineNumber,
      raw: line,
      ip: match[1],
      timestamp: match[2],
      method: match[3],
      path: match[4],
      status: parseInt(match[5], 10),
      bytes: match[6] === "-" ? 0 : parseInt(match[6], 10),
      referer: match[7] === "-" ? "" : match[7],
      userAgent: match[8],
      parsed: true,
    };
  }

  // Try common format
  match = line.match(COMMON_LOG_REGEX);
  if (match) {
    return {
      lineNumber,
      raw: line,
      ip: match[1],
      timestamp: match[2],
      method: match[3],
      path: match[4],
      status: parseInt(match[5], 10),
      bytes: match[6] === "-" ? 0 : parseInt(match[6], 10),
      referer: "",
      userAgent: "",
      parsed: true,
    };
  }

  // Return unparsed line
  return {
    lineNumber,
    raw: line,
    ip: null,
    timestamp: null,
    method: null,
    path: null,
    status: null,
    bytes: null,
    referer: null,
    userAgent: null,
    parsed: false,
  };
}

/**
 * Parse multiple log lines
 * @param {string} content - Raw log content
 * @returns {Object} Object with entries array and metadata
 */
export function parseLog(content) {
  if (!content || content.trim() === "") {
    return { entries: [], totalLines: 0, parsedLines: 0 };
  }

  const lines = content.split("\n");
  const entries = [];
  let parsedLines = 0;

  for (let i = 0; i < lines.length; i++) {
    const entry = parseLogLine(lines[i], i + 1);
    if (entry) {
      entries.push(entry);
      if (entry.parsed) {
        parsedLines++;
      }
    }
  }

  return {
    entries,
    totalLines: lines.length,
    parsedLines,
  };
}

/**
 * Check if a string is a valid IP address
 * @param {string} str - String to check
 * @returns {boolean}
 */
export function isValidIP(str) {
  return IP_REGEX.test(str);
}

/**
 * Filter log entries by grep query
 * @param {Array} entries - Log entries
 * @param {string} query - Search query
 * @returns {Array} Filtered entries
 */
export function filterByGrep(entries, query) {
  if (!query || query.trim() === "") {
    return entries;
  }

  const lowerQuery = query.toLowerCase();
  return entries.filter((entry) => entry.raw.toLowerCase().includes(lowerQuery));
}

/**
 * Filter log entries by IP addresses
 * @param {Array} entries - Log entries
 * @param {Set} hiddenIPs - IPs to hide
 * @param {Set} onlyShowIPs - If non-empty, only show these IPs
 * @returns {Array} Filtered entries
 */
export function filterByIP(entries, hiddenIPs, onlyShowIPs) {
  return entries.filter((entry) => {
    if (!entry.ip) return true; // Show unparsed lines

    if (onlyShowIPs.size > 0) {
      return onlyShowIPs.has(entry.ip);
    }

    return !hiddenIPs.has(entry.ip);
  });
}

/**
 * Get status code color class
 * @param {number} status - HTTP status code
 * @returns {string} CSS class name
 */
export function getStatusClass(status) {
  if (status >= 200 && status < 300) return "status-success";
  if (status >= 300 && status < 400) return "status-redirect";
  if (status >= 400 && status < 500) return "status-client-error";
  if (status >= 500) return "status-server-error";
  return "";
}

/**
 * Extract unique IPs from entries
 * @param {Array} entries - Log entries
 * @returns {Map} Map of IP to count
 */
export function getIPCounts(entries) {
  const counts = new Map();
  for (const entry of entries) {
    if (entry.ip) {
      counts.set(entry.ip, (counts.get(entry.ip) || 0) + 1);
    }
  }
  return counts;
}
