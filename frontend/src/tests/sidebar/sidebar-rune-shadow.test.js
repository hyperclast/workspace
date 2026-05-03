/**
 * Sidebar rune-shadow regression tests.
 *
 * Guards against a Svelte 5 footgun: when a script declares a local variable
 * whose name matches a rune (`state`, `effect`, `derived`, `props`, `bindable`,
 * `inspect`, `host`), and elsewhere in the same script calls the corresponding
 * rune (e.g. `$state(false)`), the compiler treats the rune call as a legacy
 * store auto-subscribe to the local variable. At runtime this throws
 * `TypeError: t.subscribe is not a function` and prevents the component from
 * mounting — which in turn aborts the whole app bootstrap.
 *
 * The check explicitly allows the safe idiom `let <name> = $<name>(...)` —
 * Svelte's analyzer treats the rune call as a rune when it initializes the
 * very binding it would otherwise shadow (see `// const state = $state(0)
 * is valid` in the Svelte compiler).
 */

import { describe, test, expect } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

const RUNE_NAMES = ["state", "effect", "derived", "props", "bindable", "inspect", "host"];

function getScriptBody(svelteSource) {
  const match = svelteSource.match(/<script[^>]*>([\s\S]*?)<\/script>/);
  return match ? match[1] : "";
}

function findShadowingDeclarations(scriptBody) {
  const conflicts = [];
  for (const name of RUNE_NAMES) {
    const declRegex = new RegExp(`\\b(?:const|let|var)\\s+${name}\\b\\s*(=\\s*([^;]+))?`, "g");
    let declMatch;
    while ((declMatch = declRegex.exec(scriptBody)) !== null) {
      const initializer = (declMatch[2] || "").trim();
      const safeIdiom = new RegExp(`^\\$${name}\\b`).test(initializer);
      if (safeIdiom) continue;

      const runeCallRegex = new RegExp(`\\$${name}\\s*\\(`, "g");
      const calls = scriptBody.match(runeCallRegex) || [];
      if (calls.length > 0) {
        conflicts.push({ name, declaration: declMatch[0], runeCalls: calls.length });
      }
    }
  }
  return conflicts;
}

describe("Sidebar.svelte rune-name shadowing", () => {
  const sidebarSource = readFileSync(
    resolve(__dirname, "../../lib/components/Sidebar.svelte"),
    "utf-8"
  );
  const scriptBody = getScriptBody(sidebarSource);

  test("script section is not empty", () => {
    expect(scriptBody.length).toBeGreaterThan(0);
  });

  test("no local variable named 'state' shadows the $state rune", () => {
    const conflicts = findShadowingDeclarations(scriptBody).filter((c) => c.name === "state");
    expect(
      conflicts,
      `Found shadowing declaration(s) that would compile $state(...) as a legacy ` +
        `auto-subscribe and break component mount: ${JSON.stringify(conflicts)}`
    ).toEqual([]);
  });

  test("no rune name is shadowed by a local declaration when the rune is called", () => {
    const conflicts = findShadowingDeclarations(scriptBody);
    expect(conflicts, JSON.stringify(conflicts)).toEqual([]);
  });
});

describe("Shadow detector self-tests", () => {
  test("flags `const state = something()` paired with `$state(...)`", () => {
    const buggy = `
      const state = getState();
      let flag = $state(false);
    `;
    expect(findShadowingDeclarations(buggy)).toHaveLength(1);
  });

  test("allows the `let state = $state(...)` idiom", () => {
    const safe = `
      let state = $state(getState());
    `;
    expect(findShadowingDeclarations(safe)).toHaveLength(0);
  });

  test("allows a local 'state' when no $state rune is called", () => {
    const ok = `
      let state = getPdfViewerState();
      function handle() { return state.url; }
    `;
    expect(findShadowingDeclarations(ok)).toHaveLength(0);
  });

  test("flags shadowing for any rune name", () => {
    const buggy = `
      const props = somePropsHelper();
      let foo = $props();
    `;
    expect(findShadowingDeclarations(buggy)).toHaveLength(1);
    expect(findShadowingDeclarations(buggy)[0].name).toBe("props");
  });
});
