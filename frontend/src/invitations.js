/**
 * Invitation Handling
 * Manages invitation acceptance flow for collaborative pages
 */

import { API_BASE_URL } from "./config.js";

/**
 * Show error message to user
 * @param {string} message - Error message to display
 */
function showError(message) {
  // Hide the processing message by removing it entirely
  const processingMessage = document.getElementById("processing-message");
  if (processingMessage) {
    processingMessage.remove();
  }

  // Show the error message
  const errorElement = document.getElementById("error-message");
  if (errorElement) {
    errorElement.textContent = message;
    errorElement.style.display = "block";
  } else {
    alert(message);
  }
}

/**
 * Validates invitation and handles appropriate redirect
 * @param {string} token - Invitation token from URL
 */
export async function handleInvitation(token) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/pages/invitations/${token}/validate`, {
      credentials: "same-origin",
    });

    const data = await response.json();

    if (!response.ok) {
      // Show error and redirect to home
      showError(data.message || "Failed to process invitation");
      setTimeout(() => {
        window.location.href = "/";
      }, 3000);
      return;
    }

    if (data.action === "redirect") {
      // Authenticated user - redirect to page
      window.location.href = data.redirect_to;
    } else if (data.action === "signup") {
      // Unauthenticated - redirect to signup with pre-filled email
      const params = new URLSearchParams({
        email: data.email,
        redirect: data.redirect_to,
      });
      window.location.href = `/signup?${params}`;
    }
  } catch (error) {
    console.error("Failed to validate invitation:", error);
    showError("Failed to process invitation. Please try again.");
    setTimeout(() => {
      window.location.href = "/";
    }, 3000);
  }
}
