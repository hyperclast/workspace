<script>
  import { onMount } from "svelte";
  import { getBrandName } from "../../../config.js";
  import { getSession, signup } from "../../../auth.js";
  import AuthLayout from "./AuthLayout.svelte";

  const brandName = getBrandName();

  // Get URL parameters
  const urlParams = new URLSearchParams(window.location.search);
  const redirectTo = urlParams.get("redirect") || "/";
  const prefilledEmail = urlParams.get("email") || "";

  let email = $state(prefilledEmail);
  let password = $state("");
  let error = $state("");
  let loading = $state(false);

  let passwordInput = $state(null);

  onMount(async () => {
    document.title = `Sign Up - ${brandName}`;
    // Initialize CSRF token
    try {
      await getSession();
    } catch (e) {
      console.error("Failed to initialize CSRF token:", e);
    }
    // Focus password if email is prefilled
    if (prefilledEmail && passwordInput) {
      passwordInput.focus();
    }
  });

  async function handleSubmit(e) {
    e.preventDefault();
    error = "";

    // Client-side validation
    if (password.length < 8) {
      error = "Password must be at least 8 characters long";
      return;
    }

    loading = true;

    const result = await signup(email, password);

    if (result.success) {
      if (result.emailVerificationRequired) {
        const params = new URLSearchParams({ email });
        window.location.href = `/accounts/confirm-email/?${params}`;
      } else {
        window.location.href = redirectTo;
      }
    } else {
      error = result.error;
      loading = false;
    }
  }
</script>

<AuthLayout title="Create your account" subtitle="Get started with {brandName}">
  {#if error}
    <div class="error-message">{error}</div>
  {/if}

  <form onsubmit={handleSubmit}>
    <div class="form-group">
      <label for="signup-email">Email</label>
      <input
        type="email"
        id="signup-email"
        bind:value={email}
        required
        autocomplete="email"
        placeholder="you@example.com"
        disabled={loading}
      />
    </div>

    <div class="form-group">
      <label for="signup-password">Password</label>
      <input
        type="password"
        id="signup-password"
        bind:this={passwordInput}
        bind:value={password}
        required
        autocomplete="new-password"
        minlength="8"
        placeholder="At least 8 characters"
        disabled={loading}
      />
    </div>

    <button type="submit" class="primary-btn" disabled={loading}>
      {loading ? "Creating account..." : "Create Account"}
    </button>

    <p class="auth-switch">
      Already have an account? <a href="/login/">Log in</a>
    </p>
  </form>
</AuthLayout>
