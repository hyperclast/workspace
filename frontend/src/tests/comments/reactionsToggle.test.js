/**
 * Reactions Toggle — Error Handling & Config Tests
 *
 * Source-level verification that:
 * 1. handleToggleReaction shows user-visible feedback on failure (toast)
 * 2. ALLOWED_REACTIONS is sourced from backend via getAppConfig()
 */

import { describe, test, expect } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

const source = readFileSync(
  resolve(__dirname, "../../lib/components/sidebar/CommentsTab.svelte"),
  "utf-8"
);

describe("handleToggleReaction — error handling", () => {
  test("catch block shows an error toast", () => {
    const fnMatch = source.match(/async function handleToggleReaction[\s\S]*?^  \}/m);
    expect(fnMatch).not.toBeNull();
    expect(fnMatch[0]).toContain('showToast("Couldn\'t toggle reaction", "error")');
  });

  test("catch block still logs to console for debugging", () => {
    const fnMatch = source.match(/async function handleToggleReaction[\s\S]*?^  \}/m);
    expect(fnMatch).not.toBeNull();
    expect(fnMatch[0]).toContain("console.error");
  });
});

describe("ALLOWED_REACTIONS — backend as source of truth", () => {
  test("reads from getAppConfig().reactions.allowedEmojis", () => {
    expect(source).toContain("getAppConfig().reactions?.allowedEmojis");
  });

  test("imports getAppConfig from config.js", () => {
    expect(source).toMatch(/import\s*\{[^}]*getAppConfig[^}]*\}\s*from\s*["'][^"']*config\.js["']/);
  });

  test("has a hardcoded fallback in case config is not injected", () => {
    // The ?? fallback ensures the app works even without the template config
    const line = source.match(/ALLOWED_REACTIONS\s*=\s*getAppConfig\(\).*\?\?\s*\[/);
    expect(line).not.toBeNull();
  });
});
