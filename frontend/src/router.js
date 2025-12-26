/**
 * Simple Client-Side Router
 *
 * Handles SPA routing by dynamically loading page modules based on URL path.
 * Uses a whitelist approach - only known SPA routes are handled client-side,
 * all other routes fall through to the server (proper 404 handling).
 */

// SPA route definitions - only these paths are handled client-side
const routes = {
  '/login/': () => import('./loginPage.js'),
  '/signup/': () => import('./signupPage.js'),
  '/invitation/': () => import('./invitationPage.js'),
  '/reset-password/': () => import('./resetPasswordPage.js'),
  '/forgot-password/': () => import('./forgotPasswordPage.js'),
  '/settings/': () => import('./settingsPage.js'),
};

/**
 * Extract page ID from /pages/<id>/ URL pattern
 */
export function getPageIdFromPath(path = window.location.pathname) {
  const match = path.match(/^\/pages\/([^/]+)\/?$/);
  return match ? match[1] : null;
}

/**
 * Normalize a path by ensuring it has a trailing slash (except for root)
 */
function normalizePath(path) {
  if (path !== '/' && !path.endsWith('/')) {
    return path + '/';
  }
  return path;
}

/**
 * Check if a path should be handled by the SPA router (whitelist approach)
 * Note: '/' is explicitly excluded - it should always do a full page navigation
 * so Django can handle the redirect (to landing page or first page)
 */
function isSpaRoute(path) {
  const normalizedPath = normalizePath(path);
  if (normalizedPath === '/') return false;
  return normalizedPath.startsWith('/pages/') || normalizedPath in routes;
}

/**
 * Main router function - loads the appropriate page based on current URL
 */
export async function router() {
  const path = normalizePath(window.location.pathname);

  // /pages/<id>/ pattern - load main app
  if (path.startsWith('/pages/')) {
    const module = await import('./main.js');
    if (module.default && typeof module.default === 'function') {
      await module.default();
    }
    return;
  }

  // Known SPA route
  if (routes[path]) {
    try {
      const module = await routes[path]();
      if (module.default && typeof module.default === 'function') {
        await module.default();
      }
    } catch (err) {
      console.error('Failed to load page:', err);
      window.location.href = '/';
    }
    return;
  }

  // Unknown route - let server handle it (will 404 if not found)
  // This shouldn't normally happen since we only call router() for SPA routes
}

/**
 * Navigate to a new path programmatically
 * @param {string} path - The path to navigate to
 */
export function navigate(path) {
  const normalizedPath = normalizePath(path);

  // Only handle SPA routes, otherwise do full page navigation
  if (!isSpaRoute(normalizedPath)) {
    window.location.href = normalizedPath;
    return;
  }

  window.history.pushState({}, '', normalizedPath);
  router();
}

// Handle browser back/forward buttons
window.addEventListener('popstate', router);

// Handle internal link clicks - whitelist approach
document.addEventListener('click', (e) => {
  const anchor = e.target.closest('a[href^="/"]');

  if (anchor) {
    const href = anchor.getAttribute('href');

    // Skip API routes and external links
    if (href.startsWith('/api/') || anchor.getAttribute('target') === '_blank') {
      return;
    }

    // Only intercept clicks for known SPA routes
    if (isSpaRoute(href)) {
      e.preventDefault();
      navigate(href);
    }
    // All other routes: let browser handle normally (server-rendered or 404)
  }
});
