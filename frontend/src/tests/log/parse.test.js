import { describe, it, expect } from "vitest";
import {
  parseLogLine,
  parseLog,
  isValidIP,
  filterByGrep,
  filterByIP,
  getStatusClass,
  getIPCounts,
} from "../../log/parse.js";

describe("parseLogLine", () => {
  describe("Apache/Nginx combined format", () => {
    it("parses a standard combined log entry", () => {
      const line =
        '192.168.1.1 - - [10/Oct/2023:13:55:36 -0700] "GET /index.html HTTP/1.1" 200 2326 "-" "Mozilla/5.0"';
      const result = parseLogLine(line, 1);

      expect(result).toEqual({
        lineNumber: 1,
        raw: line,
        ip: "192.168.1.1",
        timestamp: "10/Oct/2023:13:55:36 -0700",
        method: "GET",
        path: "/index.html",
        status: 200,
        bytes: 2326,
        referer: "",
        userAgent: "Mozilla/5.0",
        parsed: true,
      });
    });

    it("parses entry with referer", () => {
      const line =
        '10.0.0.1 - - [15/Nov/2023:08:00:00 +0000] "POST /api/data HTTP/1.1" 201 512 "https://example.com" "curl/7.68.0"';
      const result = parseLogLine(line, 5);

      expect(result.ip).toBe("10.0.0.1");
      expect(result.method).toBe("POST");
      expect(result.path).toBe("/api/data");
      expect(result.status).toBe(201);
      expect(result.referer).toBe("https://example.com");
      expect(result.userAgent).toBe("curl/7.68.0");
      expect(result.parsed).toBe(true);
    });

    it("handles various HTTP methods", () => {
      const methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"];

      methods.forEach((method) => {
        const line = `127.0.0.1 - - [01/Jan/2024:00:00:00 +0000] "${method} /test HTTP/1.1" 200 100 "-" "test"`;
        const result = parseLogLine(line, 1);
        expect(result.method).toBe(method);
        expect(result.parsed).toBe(true);
      });
    });

    it("handles dash for bytes (no content)", () => {
      const line =
        '192.168.1.1 - - [10/Oct/2023:13:55:36 -0700] "HEAD /check HTTP/1.1" 200 - "-" "Mozilla/5.0"';
      const result = parseLogLine(line, 1);

      expect(result.bytes).toBe(0);
      expect(result.parsed).toBe(true);
    });

    it("handles various status codes", () => {
      const statuses = [200, 201, 301, 302, 400, 401, 403, 404, 500, 502, 503];

      statuses.forEach((status) => {
        const line = `1.2.3.4 - - [01/Jan/2024:00:00:00 +0000] "GET / HTTP/1.1" ${status} 100 "-" "test"`;
        const result = parseLogLine(line, 1);
        expect(result.status).toBe(status);
      });
    });
  });

  describe("common log format (without referer/user-agent)", () => {
    it("parses common log format", () => {
      const line = '192.168.1.1 - - [10/Oct/2023:13:55:36 -0700] "GET /page HTTP/1.1" 200 1234';
      const result = parseLogLine(line, 1);

      expect(result.ip).toBe("192.168.1.1");
      expect(result.method).toBe("GET");
      expect(result.path).toBe("/page");
      expect(result.status).toBe(200);
      expect(result.bytes).toBe(1234);
      expect(result.referer).toBe("");
      expect(result.userAgent).toBe("");
      expect(result.parsed).toBe(true);
    });
  });

  describe("unparseable lines", () => {
    it("returns unparsed for empty lines", () => {
      expect(parseLogLine("", 1)).toBeNull();
      expect(parseLogLine("   ", 1)).toBeNull();
    });

    it("returns unparsed for non-log lines", () => {
      const line = "This is just some random text";
      const result = parseLogLine(line, 1);

      expect(result.raw).toBe(line);
      expect(result.parsed).toBe(false);
      expect(result.ip).toBeNull();
    });

    it("returns unparsed for partial log lines", () => {
      const line = "192.168.1.1 - - [incomplete";
      const result = parseLogLine(line, 1);

      expect(result.parsed).toBe(false);
    });
  });
});

describe("parseLog", () => {
  it("parses multiple log lines", () => {
    const content = `192.168.1.1 - - [10/Oct/2023:13:55:36 -0700] "GET /a HTTP/1.1" 200 100 "-" "Mozilla"
192.168.1.2 - - [10/Oct/2023:13:55:37 -0700] "GET /b HTTP/1.1" 404 50 "-" "Chrome"
192.168.1.1 - - [10/Oct/2023:13:55:38 -0700] "POST /c HTTP/1.1" 201 200 "-" "curl"`;

    const result = parseLog(content);

    expect(result.entries.length).toBe(3);
    expect(result.totalLines).toBe(3);
    expect(result.parsedLines).toBe(3);
  });

  it("handles mixed parsed and unparsed lines", () => {
    const content = `192.168.1.1 - - [10/Oct/2023:13:55:36 -0700] "GET /a HTTP/1.1" 200 100 "-" "Mozilla"
Some error message
192.168.1.2 - - [10/Oct/2023:13:55:37 -0700] "GET /b HTTP/1.1" 404 50 "-" "Chrome"`;

    const result = parseLog(content);

    expect(result.entries.length).toBe(3);
    expect(result.parsedLines).toBe(2);
    expect(result.entries[1].parsed).toBe(false);
  });

  it("handles empty content", () => {
    expect(parseLog("")).toEqual({ entries: [], totalLines: 0, parsedLines: 0 });
    expect(parseLog("   ")).toEqual({ entries: [], totalLines: 0, parsedLines: 0 });
  });

  it("handles content with trailing newline", () => {
    const content =
      '192.168.1.1 - - [10/Oct/2023:13:55:36 -0700] "GET /a HTTP/1.1" 200 100 "-" "Mozilla"\n';
    const result = parseLog(content);

    expect(result.entries.length).toBe(1);
  });
});

describe("isValidIP", () => {
  it("validates correct IP addresses", () => {
    expect(isValidIP("192.168.1.1")).toBe(true);
    expect(isValidIP("10.0.0.1")).toBe(true);
    expect(isValidIP("255.255.255.255")).toBe(true);
    expect(isValidIP("1.2.3.4")).toBe(true);
  });

  it("rejects invalid IP addresses", () => {
    expect(isValidIP("192.168.1")).toBe(false);
    expect(isValidIP("192.168.1.1.1")).toBe(false);
    expect(isValidIP("abc.def.ghi.jkl")).toBe(false);
    expect(isValidIP("")).toBe(false);
    expect(isValidIP("localhost")).toBe(false);
  });
});

describe("filterByGrep", () => {
  const entries = [
    { raw: "192.168.1.1 GET /index.html 200", lineNumber: 1 },
    { raw: "10.0.0.1 POST /api/users 201", lineNumber: 2 },
    { raw: "192.168.1.1 GET /about.html 200", lineNumber: 3 },
  ];

  it("filters by IP address", () => {
    const result = filterByGrep(entries, "192.168");
    expect(result.length).toBe(2);
  });

  it("filters by path", () => {
    const result = filterByGrep(entries, "/api");
    expect(result.length).toBe(1);
    expect(result[0].lineNumber).toBe(2);
  });

  it("is case-insensitive", () => {
    const result = filterByGrep(entries, "GET");
    expect(result.length).toBe(2);

    const result2 = filterByGrep(entries, "get");
    expect(result2.length).toBe(2);
  });

  it("returns all entries for empty query", () => {
    expect(filterByGrep(entries, "")).toEqual(entries);
    expect(filterByGrep(entries, "   ")).toEqual(entries);
  });

  it("returns empty array when no matches", () => {
    const result = filterByGrep(entries, "DELETE");
    expect(result.length).toBe(0);
  });
});

describe("filterByIP", () => {
  const entries = [
    { ip: "192.168.1.1", lineNumber: 1 },
    { ip: "10.0.0.1", lineNumber: 2 },
    { ip: "192.168.1.1", lineNumber: 3 },
    { ip: null, lineNumber: 4 }, // unparsed line
  ];

  it("hides specified IPs", () => {
    const hidden = new Set(["192.168.1.1"]);
    const result = filterByIP(entries, hidden, new Set());

    expect(result.length).toBe(2);
    expect(result.map((e) => e.lineNumber)).toEqual([2, 4]);
  });

  it("shows only specified IPs", () => {
    const onlyShow = new Set(["10.0.0.1"]);
    const result = filterByIP(entries, new Set(), onlyShow);

    expect(result.length).toBe(2); // includes unparsed line
    expect(result.map((e) => e.lineNumber)).toEqual([2, 4]);
  });

  it("always shows unparsed lines", () => {
    const hidden = new Set(["192.168.1.1", "10.0.0.1"]);
    const result = filterByIP(entries, hidden, new Set());

    expect(result.length).toBe(1);
    expect(result[0].lineNumber).toBe(4);
  });

  it("onlyShow takes precedence over hidden", () => {
    const hidden = new Set(["10.0.0.1"]);
    const onlyShow = new Set(["10.0.0.1"]);
    const result = filterByIP(entries, hidden, onlyShow);

    // onlyShow is checked first, so it shows 10.0.0.1 and unparsed
    expect(result.length).toBe(2);
  });
});

describe("getStatusClass", () => {
  it("returns correct class for 2xx status codes", () => {
    expect(getStatusClass(200)).toBe("status-success");
    expect(getStatusClass(201)).toBe("status-success");
    expect(getStatusClass(204)).toBe("status-success");
  });

  it("returns correct class for 3xx status codes", () => {
    expect(getStatusClass(301)).toBe("status-redirect");
    expect(getStatusClass(302)).toBe("status-redirect");
    expect(getStatusClass(304)).toBe("status-redirect");
  });

  it("returns correct class for 4xx status codes", () => {
    expect(getStatusClass(400)).toBe("status-client-error");
    expect(getStatusClass(401)).toBe("status-client-error");
    expect(getStatusClass(404)).toBe("status-client-error");
  });

  it("returns correct class for 5xx status codes", () => {
    expect(getStatusClass(500)).toBe("status-server-error");
    expect(getStatusClass(502)).toBe("status-server-error");
    expect(getStatusClass(503)).toBe("status-server-error");
  });

  it("returns empty string for unknown status codes", () => {
    expect(getStatusClass(0)).toBe("");
    expect(getStatusClass(100)).toBe("");
  });
});

describe("getIPCounts", () => {
  it("counts IP occurrences", () => {
    const entries = [
      { ip: "192.168.1.1" },
      { ip: "10.0.0.1" },
      { ip: "192.168.1.1" },
      { ip: "192.168.1.1" },
      { ip: "10.0.0.1" },
    ];

    const counts = getIPCounts(entries);

    expect(counts.get("192.168.1.1")).toBe(3);
    expect(counts.get("10.0.0.1")).toBe(2);
    expect(counts.size).toBe(2);
  });

  it("ignores entries without IP", () => {
    const entries = [{ ip: "192.168.1.1" }, { ip: null }, { ip: "192.168.1.1" }];

    const counts = getIPCounts(entries);

    expect(counts.get("192.168.1.1")).toBe(2);
    expect(counts.size).toBe(1);
  });

  it("returns empty map for empty entries", () => {
    expect(getIPCounts([]).size).toBe(0);
  });
});

describe("real-world log examples", () => {
  it("parses nginx access log format", () => {
    const line =
      '66.249.65.159 - - [06/Nov/2023:10:30:45 +0000] "GET /robots.txt HTTP/1.1" 200 67 "-" "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"';
    const result = parseLogLine(line, 1);

    expect(result.ip).toBe("66.249.65.159");
    expect(result.method).toBe("GET");
    expect(result.path).toBe("/robots.txt");
    expect(result.status).toBe(200);
    expect(result.userAgent).toContain("Googlebot");
    expect(result.parsed).toBe(true);
  });

  it("parses apache access log format", () => {
    const line =
      '203.0.113.50 - frank [10/Oct/2000:13:55:36 -0700] "GET /apache_pb.gif HTTP/1.0" 200 2326 "http://www.example.com/start.html" "Mozilla/4.08 [en] (Win98; I ;Nav)"';
    const result = parseLogLine(line, 1);

    expect(result.ip).toBe("203.0.113.50");
    expect(result.method).toBe("GET");
    expect(result.path).toBe("/apache_pb.gif");
    expect(result.status).toBe(200);
    expect(result.parsed).toBe(true);
  });

  it("handles complex paths with query strings", () => {
    const line =
      '192.168.1.1 - - [01/Jan/2024:12:00:00 +0000] "GET /search?q=test&page=1 HTTP/1.1" 200 5000 "-" "Mozilla/5.0"';
    const result = parseLogLine(line, 1);

    expect(result.path).toBe("/search?q=test&page=1");
    expect(result.parsed).toBe(true);
  });

  it("handles HTTP/2 requests", () => {
    const line =
      '192.168.1.1 - - [01/Jan/2024:12:00:00 +0000] "GET /api/v2/data HTTP/2.0" 200 1234 "-" "Mozilla/5.0"';
    const result = parseLogLine(line, 1);

    expect(result.method).toBe("GET");
    expect(result.path).toBe("/api/v2/data");
    expect(result.parsed).toBe(true);
  });
});
