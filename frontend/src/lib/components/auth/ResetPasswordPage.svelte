<script>
  import { onMount } from "svelte";
  import { API_BASE_URL, getBrandName } from "../../../config.js";
  import { getCsrfToken } from "../../../csrf.js";

  const brandName = getBrandName();

  // Get reset key from URL
  const urlParams = new URLSearchParams(window.location.search);
  const resetKey = urlParams.get("key");

  let password = $state("");
  let error = $state("");
  let loading = $state(false);
  let success = $state(false);

  onMount(() => {
    document.title = `Reset Password - ${brandName}`;

    // Redirect if no key
    if (!resetKey) {
      error = "Password reset link is invalid or missing";
      setTimeout(() => {
        window.location.href = "/login";
      }, 3000);
    }
  });

  async function handleSubmit(e) {
    e.preventDefault();
    error = "";

    if (password.length < 8) {
      error = "Password must be at least 8 characters long";
      return;
    }

    loading = true;

    try {
      // Step 1: Validate the reset key
      const validateResponse = await fetch(`${API_BASE_URL}/api/browser/v1/auth/password/reset`, {
        method: "GET",
        credentials: "same-origin",
        headers: {
          "X-Password-Reset-Key": resetKey,
        },
      });

      if (!validateResponse.ok) {
        const validateData = await validateResponse.json();
        if (validateData.errors) {
          error = Object.values(validateData.errors).flat().join(". ");
        } else {
          error = "Invalid or expired reset link. Please request a new one.";
        }
        loading = false;
        return;
      }

      await validateResponse.json();

      // Step 2: Get fresh CSRF token
      const csrfToken = getCsrfToken();

      // Step 3: Submit new password
      const response = await fetch(`${API_BASE_URL}/api/browser/v1/auth/password/reset`, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken || "",
          "X-Password-Reset-Key": resetKey,
        },
        body: JSON.stringify({
          key: resetKey,
          password: password,
        }),
      });

      const data = await response.json();

      // Success: 200 OK or 401 (password reset but not logged in)
      if (response.ok || response.status === 401) {
        success = true;
        setTimeout(() => {
          window.location.href = "/login";
        }, 3000);
      } else {
        if (data.errors) {
          error = Object.values(data.errors).flat().join(". ");
        } else {
          error = data.message || "Failed to reset password. The link may have expired.";
        }
        loading = false;
      }
    } catch (err) {
      console.error("Password reset error:", err);
      error = "An error occurred. Please try again.";
      loading = false;
    }
  }
</script>

<div class="auth-container">
  <div class="auth-box">
    <h1>Set new password</h1>
    <p class="auth-subtitle">Your new password must be at least 8 characters.</p>

    {#if error}
      <div class="error-message">{error}</div>
    {/if}

    {#if !success}
      <form onsubmit={handleSubmit}>
        <div class="form-group">
          <label for="new-password">New Password</label>
          <input
            type="password"
            id="new-password"
            bind:value={password}
            required
            autocomplete="new-password"
            minlength="8"
            placeholder="Enter your new password"
            disabled={loading || !resetKey}
          />
        </div>

        <button type="submit" class="primary-btn" disabled={loading || !resetKey}>
          {loading ? "Resetting password..." : "Reset Password"}
        </button>
      </form>
    {:else}
      <div class="success-message">
        <div class="success-icon">✓</div>
        <strong>Password updated</strong>
        <p>Your password has been reset. Redirecting to login...</p>
      </div>
    {/if}
  </div>
</div>
