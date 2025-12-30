<script>
  import { onMount } from "svelte";
  import { getBrandName } from "../../../config.js";
  import { getSession, login } from "../../../auth.js";
  import AuthLayout from "./AuthLayout.svelte";

  const brandName = getBrandName();

  let email = $state("");
  let password = $state("");
  let error = $state("");
  let loading = $state(false);

  // Get redirect URL from query params
  const urlParams = new URLSearchParams(window.location.search);
  const redirectTo = urlParams.get("redirect") || "/";

  onMount(async () => {
    document.title = `Login - ${brandName}`;
    // Initialize CSRF token
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

    const result = await login(email, password);

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

<AuthLayout title="Welcome back" subtitle="Sign in to continue to {brandName}">
  {#if error}
    <div class="error-message">{error}</div>
  {/if}

  <form onsubmit={handleSubmit}>
    <div class="form-group">
      <label for="login-email">Email</label>
      <input
        type="email"
        id="login-email"
        bind:value={email}
        required
        autocomplete="email"
        placeholder="you@example.com"
        disabled={loading}
      />
    </div>

    <div class="form-group">
      <label for="login-password">Password</label>
      <input
        type="password"
        id="login-password"
        bind:value={password}
        required
        autocomplete="current-password"
        placeholder="Your password"
        disabled={loading}
      />
    </div>

    <p class="auth-forgot">
      <a href="/forgot-password">Forgot password?</a>
    </p>

    <button type="submit" class="primary-btn" disabled={loading}>
      {loading ? "Signing in..." : "Sign In"}
    </button>

    <p class="auth-switch">
      Don't have an account? <a href="/signup">Create one</a>
    </p>
  </form>
</AuthLayout>
