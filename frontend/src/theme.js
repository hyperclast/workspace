const THEME_KEY = "hyperclast-theme";

export function getStoredTheme() {
  try {
    return localStorage.getItem(THEME_KEY) || "system";
  } catch {
    return "system";
  }
}

export function setStoredTheme(theme) {
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    // localStorage not available
  }
}

export function getSystemTheme() {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function getEffectiveTheme(stored = getStoredTheme()) {
  if (stored === "system") {
    return getSystemTheme();
  }
  return stored;
}

export function applyTheme(theme = getStoredTheme()) {
  const effective = getEffectiveTheme(theme);
  document.documentElement.setAttribute("data-theme", effective);
  document.documentElement.classList.remove("light", "dark");
  document.documentElement.classList.add(effective);
}

export function setTheme(theme) {
  setStoredTheme(theme);
  applyTheme(theme);
  window.dispatchEvent(
    new CustomEvent("themechange", { detail: { theme, effective: getEffectiveTheme(theme) } })
  );
}

export function initTheme() {
  applyTheme();

  if (typeof window !== "undefined") {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    mediaQuery.addEventListener("change", () => {
      if (getStoredTheme() === "system") {
        applyTheme("system");
      }
    });
  }
}

// Apply theme immediately to prevent flash
if (typeof document !== "undefined") {
  const stored = getStoredTheme();
  const effective =
    stored === "system"
      ? window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light"
      : stored;
  document.documentElement.setAttribute("data-theme", effective);
  document.documentElement.classList.add(effective);
}
