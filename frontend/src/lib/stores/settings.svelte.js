/**
 * Settings page store - manages user data and organizations
 */

import { API_BASE_URL } from "../../config.js";
import { csrfFetch } from "../../csrf.js";

// Reactive state
let user = $state(null);
let orgs = $state([]);
let loading = $state(true);
let error = $state(null);

// Actions
export async function loadSettings() {
  loading = true;
  error = null;

  try {
    const [userResponse, orgsResponse] = await Promise.all([
      fetch(`${API_BASE_URL}/api/users/me/`, { credentials: "same-origin" }),
      fetch(`${API_BASE_URL}/api/orgs/`, { credentials: "same-origin" }),
    ]);

    if (!userResponse.ok) {
      throw new Error("Failed to load settings");
    }

    user = await userResponse.json();
    const rawOrgs = orgsResponse.ok ? await orgsResponse.json() : [];

    // Load member details for each org
    orgs = await Promise.all(
      rawOrgs.map(async (org) => {
        try {
          const membersResponse = await fetch(
            `${API_BASE_URL}/api/orgs/${org.external_id}/members/`,
            { credentials: "same-origin" }
          );
          const members = membersResponse.ok ? await membersResponse.json() : [];
          const currentMember = members.find((m) => m.email === user.email);
          return {
            ...org,
            members,
            memberCount: members.length,
            userRole: currentMember?.role || "member",
            joinedAt: currentMember?.created,
          };
        } catch {
          return { ...org, members: [], memberCount: 0, userRole: "member" };
        }
      })
    );

    loading = false;
  } catch (e) {
    console.error("Error loading settings:", e);
    error = "Failed to load settings. Please try again.";
    loading = false;
  }
}

export async function updateUserField(field, value) {
  try {
    const response = await csrfFetch(`${API_BASE_URL}/api/users/me/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [field]: value }),
    });

    if (response.ok) {
      const data = await response.json();
      user = { ...user, [field]: value };
      return { success: true };
    } else {
      const data = await response.json();
      return { success: false, error: data.message || `Failed to update ${field}` };
    }
  } catch {
    return { success: false, error: `Failed to update ${field}` };
  }
}

export async function updateOrgName(orgId, newName) {
  try {
    const response = await csrfFetch(`${API_BASE_URL}/api/orgs/${orgId}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newName }),
    });

    if (response.ok) {
      orgs = orgs.map((org) =>
        org.external_id === orgId ? { ...org, name: newName } : org
      );
      return { success: true };
    } else {
      const data = await response.json();
      return { success: false, error: data.message || "Failed to update organization" };
    }
  } catch {
    return { success: false, error: "Failed to update organization" };
  }
}

export async function addOrgMember(orgId, email) {
  try {
    const response = await csrfFetch(`${API_BASE_URL}/api/orgs/${orgId}/members/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });

    if (response.ok) {
      const data = await response.json();
      // Update member count
      orgs = orgs.map((org) =>
        org.external_id === orgId
          ? { ...org, memberCount: org.memberCount + 1 }
          : org
      );
      return { success: true, data };
    } else if (response.status === 429) {
      return { success: false, error: "You're adding members too quickly. Please wait a moment." };
    } else {
      const data = await response.json();
      return { success: false, error: data.message || data.detail || "Failed to add member" };
    }
  } catch {
    return { success: false, error: "Network error. Please try again." };
  }
}

export async function regenerateToken() {
  try {
    const response = await csrfFetch(`${API_BASE_URL}/api/users/me/token/regenerate/`, {
      method: "POST",
    });

    if (response.ok) {
      const data = await response.json();
      user = { ...user, access_token: data.access_token };
      return { success: true };
    } else {
      return { success: false, error: "Failed to regenerate token" };
    }
  } catch {
    return { success: false, error: "Failed to regenerate token" };
  }
}

export async function logout() {
  try {
    await csrfFetch(`${API_BASE_URL}/api/_allauth/browser/v1/auth/session`, {
      method: "DELETE",
    });
  } catch (error) {
    console.error("Logout error:", error);
  }
  window.location.href = "/login";
}

// Export reactive state directly for Svelte components
export function getState() {
  return {
    get user() { return user; },
    get orgs() { return orgs; },
    get loading() { return loading; },
    get error() { return error; },
  };
}
