// Simple module-level state for auth tracking
// Using plain JS since we don't need Svelte reactivity for these flags
let isLoggedOut = false;
let loginToastShown = false;

export function getAuthState() {
  return { isLoggedOut, loginToastShown };
}

export function markLoggedOut() {
  isLoggedOut = true;
}

export function markLoginToastShown() {
  loginToastShown = true;
}

export function resetAuthState() {
  isLoggedOut = false;
  loginToastShown = false;
}

export function getLoginUrl() {
  const currentPath = window.location.pathname + window.location.search;
  return `/login/?next=${encodeURIComponent(currentPath)}`;
}
