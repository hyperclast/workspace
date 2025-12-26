/**
 * Application Entry Point
 *
 * This is the main entry point for the SPA.
 * It initializes the client-side router which handles all page routing.
 */

// Import global styles - must be in entry point so CSS is always available
import './style.css';

import { router } from './router.js';

// Initialize the router when the DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', router);
} else {
  router();
}
