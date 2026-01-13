<script>
  import { onMount } from "svelte";
  import { API_BASE_URL, getBrandName } from "../../../config.js";
  import { getSession } from "../../../auth.js";
  import { getCsrfToken } from "../../../csrf.js";

  const brandName = getBrandName();

  let email = $state("");
  let error = $state("");
  let loading = $state(false);
  let success = $state(false);

  onMount(async () => {
    document.title = `Forgot Password - ${brandName}`;
    try {
      await getSession();
    } catch (e) {
      console.error("Failed to initialize CSRF token:", e);
    }
  });

  async function handleSubmit(e) {
    e.preventDefault();
    error = "";
    loading = true;

    try {
      const csrfToken = getCsrfToken();
      const response = await fetch(`${API_BASE_URL}/api/browser/v1/auth/password/request`, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken || "",
        },
        body: JSON.stringify({ email }),
      });

      if (response.ok) {
        success = true;
      } else {
        const data = await response.json();
        if (data.errors) {
          error = Object.values(data.errors).flat().join(". ");
        } else {
          error = data.message || "Failed to send reset link. Please try again.";
        }
        loading = false;
      }
    } catch (err) {
      console.error("Forgot password error:", err);
      error = "An error occurred. Please try again.";
      loading = false;
    }
  }
</script>

<div class="auth-container">
  <div class="auth-box">
    <h1>Forgot password?</h1>
    <p class="auth-subtitle">No worries, we'll send you reset instructions.</p>

    {#if error}
      <div class="error-message">{error}</div>
    {/if}

    {#if !success}
      <form onsubmit={handleSubmit}>
        <div class="form-group">
          <label for="email">Email</label>
          <input
            type="email"
            id="email"
            bind:value={email}
            required
            autocomplete="email"
            placeholder="you@example.com"
            disabled={loading}
          />
        </div>

        <button type="submit" class="primary-btn" disabled={loading}>
          {loading ? "Sending..." : "Send Reset Link"}
        </button>

        <p class="auth-switch">
          <a href="/login/">← Back to login</a>
        </p>
      </form>
    {:else}
      <div class="success-message success-message-large">
        <div class="success-icon">✓</div>
        <strong>Check your email</strong>
        <p>We've sent a password reset link to your email address.</p>
      </div>
    {/if}
  </div>
</div>
