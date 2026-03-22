import { formatRelativeTime, formatBytes } from "../../lib/formatters";

describe("formatRelativeTime", () => {
  it("returns 'just now' for times less than 1 minute ago", () => {
    const date = new Date(Date.now() - 30000).toISOString();
    expect(formatRelativeTime(date)).toBe("just now");
  });

  it("returns minutes for times less than 1 hour ago", () => {
    const date = new Date(Date.now() - 5 * 60000).toISOString();
    expect(formatRelativeTime(date)).toBe("5m ago");
  });

  it("returns hours for times less than 1 day ago", () => {
    const date = new Date(Date.now() - 3 * 3600000).toISOString();
    expect(formatRelativeTime(date)).toBe("3h ago");
  });

  it("returns days for times less than 30 days ago", () => {
    const date = new Date(Date.now() - 7 * 86400000).toISOString();
    expect(formatRelativeTime(date)).toBe("7d ago");
  });

  it("returns locale date string for times 30+ days ago", () => {
    const date = new Date(Date.now() - 60 * 86400000).toISOString();
    const result = formatRelativeTime(date);
    expect(result).not.toContain("d ago");
  });
});

describe("formatBytes", () => {
  it("returns '0 B' for zero bytes", () => {
    expect(formatBytes(0)).toBe("0 B");
  });

  it("formats bytes", () => {
    expect(formatBytes(500)).toBe("500 B");
  });

  it("formats kilobytes", () => {
    expect(formatBytes(1024)).toBe("1 KB");
  });

  it("formats megabytes with decimal", () => {
    expect(formatBytes(1572864)).toBe("1.5 MB");
  });

  it("formats gigabytes", () => {
    expect(formatBytes(1073741824)).toBe("1 GB");
  });
});
