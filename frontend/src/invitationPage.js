/**
 * Invitation Page Module
 * Router-compatible module that handles invitation acceptance
 */

import { getBrandName } from "./config.js";
import { handleInvitation } from "./invitations.js";

/**
 * Initialize the invitation page
 * Renders the invitation processing UI and handles the invitation
 */
export default function initInvitationPage() {
  const brandName = getBrandName();

  // Set page title
  document.title = `Processing Invitation - ${brandName}`;

  // Render the invitation page HTML
  const app = document.getElementById("app");
  app.innerHTML = `
    <div class="auth-container">
      <div class="auth-box">
        <h1>Processing Invitation</h1>
        <p id="processing-message">Please wait while we process your invitation...</p>
        <div id="error-message" class="error-message" style="display: none;"></div>
      </div>
    </div>
  `;

  // Get token from URL
  const urlParams = new URLSearchParams(window.location.search);
  const token = urlParams.get("token");

  if (!token) {
    window.location.href = "/?error=missing_token";
  } else {
    handleInvitation(token);
  }
}
