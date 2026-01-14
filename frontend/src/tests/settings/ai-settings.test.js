import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";

describe("AI Settings - UsageChart data processing", () => {
  const DAYS_TO_SHOW = 30;
  const MIN_Y_AXIS = 10;

  function generateChartData(usageDaily, today = new Date()) {
    const data = [];
    const todayDate = new Date(today);
    todayDate.setHours(0, 0, 0, 0);

    for (let i = DAYS_TO_SHOW - 1; i >= 0; i--) {
      const date = new Date(todayDate);
      date.setDate(date.getDate() - i);
      const dateStr = date.toISOString().split("T")[0];
      const existing = usageDaily?.find((d) => d.date === dateStr);
      data.push({
        date: dateStr,
        requests: existing?.requests || 0,
      });
    }
    return data;
  }

  function calculateMaxY(chartData) {
    const maxRequests = Math.max(...chartData.map((d) => d.requests), 0);
    return Math.max(maxRequests, MIN_Y_AXIS);
  }

  function calculateYAxisTicks(maxY) {
    if (maxY <= 10) return [0, 5, 10];
    if (maxY <= 50) return [0, 25, 50];
    if (maxY <= 100) return [0, 50, 100];
    const step = Math.ceil(maxY / 4 / 10) * 10;
    return [0, step, step * 2, step * 3, Math.ceil(maxY / 10) * 10];
  }

  test("generates 30 days of data even when usage data is empty", () => {
    const chartData = generateChartData([]);

    expect(chartData).toHaveLength(30);
    expect(chartData.every((d) => d.requests === 0)).toBe(true);
  });

  test("generates 30 days of data even when usage data is undefined", () => {
    const chartData = generateChartData(undefined);

    expect(chartData).toHaveLength(30);
  });

  test("fills in missing days with zero requests", () => {
    const today = new Date("2024-01-15");
    const usageDaily = [{ date: "2024-01-10", requests: 5 }];

    const chartData = generateChartData(usageDaily, today);

    const jan10 = chartData.find((d) => d.date === "2024-01-10");
    expect(jan10.requests).toBe(5);

    const jan11 = chartData.find((d) => d.date === "2024-01-11");
    expect(jan11.requests).toBe(0);
  });

  test("maxY is at least MIN_Y_AXIS (10) even with no data", () => {
    const chartData = generateChartData([]);
    const maxY = calculateMaxY(chartData);

    expect(maxY).toBe(10);
  });

  test("maxY reflects actual max when data exceeds MIN_Y_AXIS", () => {
    const today = new Date("2024-01-15");
    const usageDaily = [
      { date: "2024-01-10", requests: 50 },
      { date: "2024-01-11", requests: 25 },
    ];

    const chartData = generateChartData(usageDaily, today);
    const maxY = calculateMaxY(chartData);

    expect(maxY).toBe(50);
  });

  test("yAxisTicks for data with no requests shows [0, 5, 10]", () => {
    const ticks = calculateYAxisTicks(10);
    expect(ticks).toEqual([0, 5, 10]);
  });

  test("yAxisTicks for data up to 50 shows [0, 25, 50]", () => {
    const ticks = calculateYAxisTicks(50);
    expect(ticks).toEqual([0, 25, 50]);
  });

  test("yAxisTicks for data up to 100 shows [0, 50, 100]", () => {
    const ticks = calculateYAxisTicks(100);
    expect(ticks).toEqual([0, 50, 100]);
  });

  test("yAxisTicks scales appropriately for larger values", () => {
    const ticks = calculateYAxisTicks(200);
    expect(ticks[0]).toBe(0);
    expect(ticks[ticks.length - 1]).toBeGreaterThanOrEqual(200);
  });

  test("chart data is ordered chronologically", () => {
    const today = new Date("2024-01-15");
    const chartData = generateChartData([], today);

    for (let i = 1; i < chartData.length; i++) {
      const prevDate = new Date(chartData[i - 1].date);
      const currDate = new Date(chartData[i].date);
      expect(currDate.getTime()).toBeGreaterThan(prevDate.getTime());
    }
  });
});

describe("AI Settings - Provider card enable/disable logic", () => {
  function canBeEnabled(hasKey, isValidated) {
    return hasKey && isValidated;
  }

  function determineIsEnabled(config, canBeEnabled) {
    if (!config) return false;
    return canBeEnabled && (config.is_enabled ?? false);
  }

  test("provider cannot be enabled without API key", () => {
    const result = canBeEnabled(false, true);
    expect(result).toBe(false);
  });

  test("provider cannot be enabled when key is not validated", () => {
    const result = canBeEnabled(true, false);
    expect(result).toBe(false);
  });

  test("provider can be enabled when key exists and is validated", () => {
    const result = canBeEnabled(true, true);
    expect(result).toBe(true);
  });

  test("isEnabled is false when config is null", () => {
    const result = determineIsEnabled(null, true);
    expect(result).toBe(false);
  });

  test("isEnabled respects canBeEnabled check", () => {
    const config = { is_enabled: true };
    expect(determineIsEnabled(config, false)).toBe(false);
    expect(determineIsEnabled(config, true)).toBe(true);
  });

  test("isEnabled defaults to false when not set in config", () => {
    const config = {};
    const result = determineIsEnabled(config, true);
    expect(result).toBe(false);
  });
});

describe("AI Settings - Key hint generation", () => {
  function getKeyHint(apiKey) {
    if (!apiKey) return null;
    if (apiKey.length <= 8) return "****";
    return `${apiKey.slice(0, 3)}...${apiKey.slice(-4)}`;
  }

  test("returns null for empty key", () => {
    expect(getKeyHint("")).toBe(null);
    expect(getKeyHint(null)).toBe(null);
    expect(getKeyHint(undefined)).toBe(null);
  });

  test("returns **** for short keys (8 chars or less)", () => {
    expect(getKeyHint("short")).toBe("****");
    expect(getKeyHint("12345678")).toBe("****");
  });

  test("masks long keys showing first 3 and last 4 chars", () => {
    expect(getKeyHint("sk-proj-abcdefghij")).toBe("sk-...ghij");
    expect(getKeyHint("anthropic-key-123456")).toBe("ant...3456");
  });
});

describe("AI Settings - Custom provider wizard validation", () => {
  function validateProviderName(name) {
    if (!name || !name.trim()) {
      return { valid: false, error: "Provider name is required" };
    }
    return { valid: true, error: null };
  }

  function validateApiBaseUrl(url) {
    if (!url || !url.trim()) {
      return { valid: false, error: "API Base URL is required" };
    }
    try {
      const parsed = new URL(url);
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
        return { valid: false, error: "URL must use http or https protocol" };
      }
      return { valid: true, error: null };
    } catch {
      return { valid: false, error: "Please enter a valid URL" };
    }
  }

  test("provider name validation requires non-empty value", () => {
    expect(validateProviderName("").valid).toBe(false);
    expect(validateProviderName("   ").valid).toBe(false);
    expect(validateProviderName(null).valid).toBe(false);
  });

  test("provider name validation passes for valid names", () => {
    expect(validateProviderName("My Provider").valid).toBe(true);
    expect(validateProviderName("Azure OpenAI").valid).toBe(true);
  });

  test("API base URL validation requires non-empty value", () => {
    expect(validateApiBaseUrl("").valid).toBe(false);
    expect(validateApiBaseUrl("   ").valid).toBe(false);
  });

  test("API base URL validation rejects invalid URLs", () => {
    expect(validateApiBaseUrl("not-a-url").valid).toBe(false);
    expect(validateApiBaseUrl("ftp://invalid").valid).toBe(false);
  });

  test("API base URL validation accepts valid URLs", () => {
    expect(validateApiBaseUrl("https://api.example.com").valid).toBe(true);
    expect(validateApiBaseUrl("http://localhost:11434/v1").valid).toBe(true);
    expect(validateApiBaseUrl("https://api.openai.azure.com/").valid).toBe(true);
  });
});

describe("AI Settings - Scope tab selection", () => {
  test("can switch between personal and organization scope", () => {
    let scope = "user";

    const switchToOrg = () => {
      scope = "org";
    };
    const switchToUser = () => {
      scope = "user";
    };

    expect(scope).toBe("user");

    switchToOrg();
    expect(scope).toBe("org");

    switchToUser();
    expect(scope).toBe("user");
  });

  test("org selector only appears when scope is org", () => {
    const shouldShowOrgSelector = (scope, hasAdminOrgs) => {
      return scope === "org" && hasAdminOrgs;
    };

    expect(shouldShowOrgSelector("user", true)).toBe(false);
    expect(shouldShowOrgSelector("org", false)).toBe(false);
    expect(shouldShowOrgSelector("org", true)).toBe(true);
  });

  test("default org is selected when switching to org scope", () => {
    const adminOrgs = [
      { external_id: "org1", name: "Org 1" },
      { external_id: "org2", name: "Org 2" },
    ];

    let selectedOrgId = null;

    const handleScopeChange = (newScope) => {
      if (newScope === "org" && adminOrgs.length > 0 && !selectedOrgId) {
        selectedOrgId = adminOrgs[0].external_id;
      }
    };

    handleScopeChange("org");

    expect(selectedOrgId).toBe("org1");
  });
});

describe("AI Settings - Provider default handling", () => {
  test("setting a provider as default clears other defaults (client logic)", () => {
    const configs = [
      { external_id: "1", provider: "openai", is_default: true },
      { external_id: "2", provider: "anthropic", is_default: false },
    ];

    const setAsDefault = (configs, configId) => {
      return configs.map((c) => ({
        ...c,
        is_default: c.external_id === configId,
      }));
    };

    const updated = setAsDefault(configs, "2");

    expect(updated.find((c) => c.external_id === "1").is_default).toBe(false);
    expect(updated.find((c) => c.external_id === "2").is_default).toBe(true);
  });

  test("can have no default provider", () => {
    const configs = [
      { external_id: "1", is_default: false },
      { external_id: "2", is_default: false },
    ];

    const hasDefault = configs.some((c) => c.is_default);
    expect(hasDefault).toBe(false);
  });
});

describe("AI Settings - Number formatting for usage stats", () => {
  function formatNumber(num) {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
    return num.toString();
  }

  test("formats small numbers without suffix", () => {
    expect(formatNumber(0)).toBe("0");
    expect(formatNumber(100)).toBe("100");
    expect(formatNumber(999)).toBe("999");
  });

  test("formats thousands with K suffix", () => {
    expect(formatNumber(1000)).toBe("1.0K");
    expect(formatNumber(1500)).toBe("1.5K");
    expect(formatNumber(999999)).toBe("1000.0K");
  });

  test("formats millions with M suffix", () => {
    expect(formatNumber(1000000)).toBe("1.0M");
    expect(formatNumber(2500000)).toBe("2.5M");
  });
});

describe("AI Settings - Date formatting", () => {
  test("formats dates for chart labels", () => {
    const formatDate = (dateStr) => {
      const date = new Date(dateStr);
      return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    };

    expect(formatDate("2024-01-15")).toBe("Jan 15");
    expect(formatDate("2024-12-31")).toBe("Dec 31");
  });
});

describe("AI Settings - Bar height calculation", () => {
  function getBarHeight(requests, maxY) {
    if (maxY === 0) return 0;
    return (requests / maxY) * 100;
  }

  test("returns 0 when maxY is 0", () => {
    expect(getBarHeight(50, 0)).toBe(0);
  });

  test("calculates correct percentage", () => {
    expect(getBarHeight(50, 100)).toBe(50);
    expect(getBarHeight(25, 100)).toBe(25);
    expect(getBarHeight(100, 100)).toBe(100);
  });

  test("handles zero requests", () => {
    expect(getBarHeight(0, 100)).toBe(0);
  });
});
