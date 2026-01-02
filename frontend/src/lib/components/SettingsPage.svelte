<script>
  import { onMount } from "svelte";
  import { getBrandName, getCsrfToken, isPrivateFeatureEnabled } from "../../config.js";
  import { getGravatarUrl, setupUserAvatar } from "../../gravatar.js";
  import { confirm, prompt } from "../modal.js";
  import {
    addOrgMember,
    getState,
    loadSettings,
    logout,
    regenerateToken,
    updateOrgName,
    updateUserField,
  } from "../stores/settings.svelte.js";
  import { showToast } from "../toast.js";
  import { validateUsername } from "../validators.js";
  import AISettingsTab from "./settings/AISettingsTab.svelte";

  const brandName = getBrandName();
  const pricingEnabled = isPrivateFeatureEnabled("pricing");
  const billingEnabled = isPrivateFeatureEnabled("billing");

  const data = getState();

  let activeTab = $state("account");
  let userMenuOpen = $state(false);
  let gravatarUrl = $state(null);
  let gravatarLoaded = $state(false);

  const editIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>`;
  const codeIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>`;
  const chevronIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>`;

  const navItems = [
    { id: "account", label: "Account", icon: "user" },
    { id: "org", label: "Organizations", icon: "building" },
    { id: "ai", label: "AI", icon: "sparkles" },
    { id: "developer", label: "Developer", icon: "code" },
  ];

  onMount(() => {
    document.title = `Settings - ${brandName}`;
    loadSettings();

    const getTabFromHash = () => {
      const hash = window.location.hash.slice(1);
      const validTabs = navItems.map((item) => item.id);
      return validTabs.includes(hash) ? hash : "account";
    };

    activeTab = getTabFromHash();

    const handleHashChange = () => {
      activeTab = getTabFromHash();
    };

    window.addEventListener("hashchange", handleHashChange);

    return () => {
      window.removeEventListener("hashchange", handleHashChange);
    };
  });

  $effect(() => {
    if (data.user?.email) {
      const avatarEl = document.getElementById("user-avatar");
      const initialEl = document.getElementById("user-initial");
      if (avatarEl && initialEl) {
        setupUserAvatar(data.user.email, avatarEl, initialEl);
      }

      const url = getGravatarUrl(data.user.email, 128);
      const img = new Image();
      img.onload = () => {
        gravatarUrl = url;
        gravatarLoaded = true;
      };
      img.onerror = () => {
        gravatarUrl = null;
        gravatarLoaded = false;
      };
      img.src = url;
    }
  });

  function switchTab(tab) {
    activeTab = tab;
    history.replaceState(null, "", `#${tab}`);
  }

  function toggleUserMenu(e) {
    e.stopPropagation();
    userMenuOpen = !userMenuOpen;
  }

  function closeUserMenu() {
    userMenuOpen = false;
  }

  function handleLogout() {
    logout();
  }

  async function editUsername() {
    const newValue = await prompt({
      title: "Edit Username",
      label: "Username",
      placeholder: "Choose a memorable username",
      value: data.user?.username || "",
      confirmText: "Save",
      required: true,
      maxlength: 20,
      validate: validateUsername,
    });

    if (newValue === null || newValue === data.user?.username) return;

    const result = await updateUserField("username", newValue);
    if (result.success) {
      showToast("Username updated");
    } else {
      showToast(result.error, "error");
    }
  }

  async function editFirstName() {
    const newValue = await prompt({
      title: "Edit First Name",
      label: "First name",
      value: data.user?.first_name || "",
      confirmText: "Save",
      required: false,
    });

    if (newValue === null) return;

    const result = await updateUserField("first_name", newValue);
    if (result.success) {
      showToast("First name updated");
    } else {
      showToast(result.error, "error");
    }
  }

  async function editLastName() {
    const newValue = await prompt({
      title: "Edit Last Name",
      label: "Last name",
      value: data.user?.last_name || "",
      confirmText: "Save",
      required: false,
    });

    if (newValue === null) return;

    const result = await updateUserField("last_name", newValue);
    if (result.success) {
      showToast("Last name updated");
    } else {
      showToast(result.error, "error");
    }
  }

  async function handleRenameOrg(e, org) {
    e.stopPropagation();

    const newName = await prompt({
      title: "Rename Organization",
      label: "Organization name",
      value: org.name,
      confirmText: "Save",
      required: true,
    });

    if (newName === null || newName === org.name) return;

    const result = await updateOrgName(org.external_id, newName);
    if (result.success) {
      showToast("Organization renamed");
    } else {
      showToast(result.error, "error");
    }
  }

  async function handleAddMember(e, org) {
    e.stopPropagation();

    const email = await prompt({
      title: "Add Member",
      label: `Invite to ${org.name}`,
      placeholder: "user@example.com",
      value: "",
      confirmText: "Add Member",
      required: true,
    });

    if (!email) return;

    if (!email.includes("@")) {
      showToast("Please enter a valid email address", "error");
      return;
    }

    const result = await addOrgMember(org.external_id, email);
    if (result.success) {
      showToast(`${result.data.email} has been added to the organization`);
    } else {
      showToast(result.error, "error");
    }
  }

  async function copyToken() {
    try {
      await navigator.clipboard.writeText(data.user?.access_token || "");
      showToast("Token copied to clipboard!");
    } catch (err) {
      console.error("Failed to copy:", err);
      showToast("Failed to copy token", "error");
    }
  }

  async function handleRegenerateToken() {
    const confirmed = await confirm({
      title: "Regenerate Token",
      message: "Are you sure you want to regenerate your API access token?",
      description:
        "Your current token will be invalidated immediately. Any applications using the current token will stop working.",
      confirmText: "Regenerate Token",
      danger: true,
    });

    if (!confirmed) return;

    const result = await regenerateToken();
    if (result.success) {
      showToast("Token regenerated successfully!");
    } else {
      showToast(result.error, "error");
    }
  }

  function formatDate(dateString) {
    if (!dateString) return "—";
    const date = new Date(dateString);
    return date.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  }

  function handleGlobalClick() {
    closeUserMenu();
  }

  function getNavIcon(icon) {
    const icons = {
      user: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>`,
      building: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"></rect><path d="M9 22v-4h6v4"></path><path d="M8 6h.01"></path><path d="M16 6h.01"></path><path d="M12 6h.01"></path><path d="M12 10h.01"></path><path d="M12 14h.01"></path><path d="M16 10h.01"></path><path d="M16 14h.01"></path><path d="M8 10h.01"></path><path d="M8 14h.01"></path></svg>`,
      sparkles: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"></path><path d="M5 3v4"></path><path d="M19 17v4"></path><path d="M3 5h4"></path><path d="M17 19h4"></path></svg>`,
      code: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>`,
    };
    return icons[icon] || "";
  }
</script>

<svelte:document onclick={handleGlobalClick} />

<div class="settings-page-wrapper">
  <nav>
    <div class="nav-brand">
      <a href="/" class="nav-title" style="text-decoration: none; color: inherit; display: flex; align-items: center; gap: 0.5rem;">
        <svg class="logo-icon" viewBox="0 0 90 90" width="24" height="24">
          <path
            d="M 10,80 L 10,70 L 20,70 L 20,80 L 30,80 L 40,80 L 40,70 L 30,70 L 30,60 L 40,60 L 40,50 L 30,50 L 20,50 L 20,60 L 10,60 L 10,50 L 10,40 L 20,40 L 20,30 L 10,30 L 10,20 L 10,10 L 20,10 L 20,20 L 30,20 L 30,10 L 40,10 L 40,20 L 40,30 L 30,30 L 30,40 L 40,40 L 50,40 L 60,40 L 60,30 L 50,30 L 50,20 L 50,10 L 60,10 L 60,20 L 70,20 L 70,10 L 80,10 L 80,20 L 80,30 L 70,30 L 70,40 L 80,40 L 80,50 L 80,60 L 70,60 L 70,50 L 60,50 L 50,50 L 50,60 L 60,60 L 60,70 L 50,70 L 50,80 L 60,80 L 70,80 L 70,70 L 80,70 L 80,80"
            fill="none"
            stroke="currentColor"
            stroke-width="6"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
        {brandName}
      </a>
    </div>
    <div class="nav-main">
      <div class="nav-actions">
        <a href="/" class="nav-link">Home</a>
        <div class="user-menu">
          <button id="user-avatar" class="user-avatar" title="Account menu" onclick={toggleUserMenu}>
            <span id="user-initial"></span>
          </button>
          <div id="user-dropdown" class="user-dropdown" class:open={userMenuOpen}>
            <div class="user-dropdown-header">
              <div class="user-dropdown-email">{data.user?.email || ""}</div>
            </div>
            <div class="user-dropdown-menu">
              <span class="user-dropdown-item nav-current">Settings</span>
              <button class="user-dropdown-item" onclick={handleLogout}>Log out</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </nav>

  <div class="settings-layout">
    <aside class="settings-sidebar">
      <h1 class="settings-sidebar-title">Settings</h1>
      <nav class="settings-nav">
        {#each navItems as item}
          <button
            class="settings-nav-item"
            class:active={activeTab === item.id}
            onclick={() => switchTab(item.id)}
          >
            <span class="nav-icon">{@html getNavIcon(item.icon)}</span>
            <span class="nav-label">{item.label}</span>
          </button>
        {/each}
      </nav>
    </aside>

    <main class="settings-main">
      {#if data.loading}
        <div class="loading-message">Loading settings...</div>
      {:else if data.error}
        <div class="error-message" style="display: block;">{data.error}</div>
      {:else}
        <!-- Account Tab -->
        <div class="settings-tab-content" class:active={activeTab === "account"}>
          <h2 class="settings-page-title">Account</h2>
          <section class="settings-section">
            <div class="settings-profile-picture">
              <div class="profile-avatar">
                {#if gravatarLoaded && gravatarUrl}
                  <img src={gravatarUrl} alt="" />
                {:else}
                  <span class="profile-initial"
                    >{data.user?.email?.charAt(0).toUpperCase() || "?"}</span
                  >
                {/if}
              </div>
              <div class="profile-picture-info">
                <span class="settings-label">Profile Picture</span>
                <p class="profile-picture-hint">
                  Your profile picture is managed through Gravatar.
                  <a href="https://gravatar.com/profile" target="_blank" rel="noopener"
                    >Change it on Gravatar</a
                  >
                </p>
              </div>
            </div>
            <div class="settings-field">
              <span class="settings-label">Username</span>
              <div class="settings-value-editable">
                <span>{data.user?.username || "—"}</span>
                <button class="settings-edit-btn" title="Edit username" onclick={editUsername}>
                  {@html editIcon}
                </button>
              </div>
            </div>
            <div class="settings-field">
              <span class="settings-label">First Name</span>
              <div class="settings-value-editable">
                <span>{data.user?.first_name || "—"}</span>
                <button class="settings-edit-btn" title="Edit first name" onclick={editFirstName}>
                  {@html editIcon}
                </button>
              </div>
            </div>
            <div class="settings-field">
              <span class="settings-label">Last Name</span>
              <div class="settings-value-editable">
                <span>{data.user?.last_name || "—"}</span>
                <button class="settings-edit-btn" title="Edit last name" onclick={editLastName}>
                  {@html editIcon}
                </button>
              </div>
            </div>
            <div class="settings-field">
              <span class="settings-label">Email</span>
              <div class="settings-value settings-email-field">
                <span>{data.user?.email || ""}</span>
                <span
                  class="email-badge"
                  class:email-verified={data.user?.email_verified}
                  class:email-unverified={!data.user?.email_verified}
                >
                  {data.user?.email_verified ? "Verified" : "Unverified"}
                </span>
              </div>
            </div>
          </section>

          <section class="settings-section settings-logout-section">
            <button class="settings-logout-btn" onclick={handleLogout}>Log out</button>
          </section>
        </div>

        <!-- Organizations Tab -->
        <div class="settings-tab-content" class:active={activeTab === "org"}>
          <h2 class="settings-page-title">Organizations</h2>
          <section class="settings-section">
            <p class="settings-tab-intro">
              Organizations you belong to. Projects and pages are organized within these.
            </p>
            <div class="orgs-list">
              {#if data.orgs.length === 0}
                <div class="orgs-empty">
                  <p>You're not a member of any organization yet.</p>
                </div>
              {:else}
                {#each data.orgs as org (org.external_id)}
                  <div class="org-card">
                    <div class="org-card-header">
                      <div class="org-card-title">
                        <span class="org-name">{org.name}</span>
                        <span
                          class="org-role-badge"
                          class:role-admin={org.userRole === "admin"}
                          class:role-member={org.userRole !== "admin"}
                        >
                          {org.userRole === "admin" ? "Admin" : "Member"}
                        </span>
                        {#if !org.domain}
                          <span class="org-personal-badge">Personal</span>
                        {/if}
                      </div>
                    </div>
                    <div class="org-card-details">
                      <div class="org-card-details-row">
                        {#if org.domain}
                          <div class="org-detail">
                            <span class="org-detail-label">Domain</span>
                            <span class="org-detail-value org-domain">@{org.domain}</span>
                          </div>
                        {/if}
                        <div class="org-detail">
                          <span class="org-detail-label">Members</span>
                          <span class="org-detail-value">{org.memberCount}</span>
                        </div>
                        <div class="org-detail">
                          <span class="org-detail-label">Created</span>
                          <span class="org-detail-value">{formatDate(org.created)}</span>
                        </div>
                        <div class="org-detail">
                          <span class="org-detail-label">Joined</span>
                          <span class="org-detail-value">{formatDate(org.joinedAt)}</span>
                        </div>
                        {#if billingEnabled}
                          <div class="org-detail org-billing-detail">
                            <span class="org-detail-label">Plan</span>
                            <span class="org-detail-value">
                              {#if org.is_pro}
                                <span class="org-plan-badge org-plan-pro">Pro</span>
                              {:else}
                                <span class="org-plan-badge org-plan-free">Free</span>
                              {/if}
                            </span>
                          </div>
                        {/if}
                      </div>
                      <div class="org-card-actions">
                        <button class="org-action-btn" onclick={(e) => handleAddMember(e, org)}>
                          Add Member
                        </button>
                        {#if billingEnabled && !org.is_pro}
                          <a href="/pricing/#hosted" class="org-action-btn org-action-btn-primary">Upgrade</a>
                        {:else if billingEnabled && org.is_pro}
                          <form action="/billing/portal/" method="POST" style="display: inline;">
                            <input
                              type="hidden"
                              name="csrfmiddlewaretoken"
                              value={getCsrfToken()}
                            />
                            <input type="hidden" name="org_id" value={org.external_id} />
                            <button type="submit" class="org-action-btn">Manage Billing</button>
                          </form>
                        {/if}
                      </div>
                    </div>
                  </div>
                {/each}
              {/if}
            </div>
          </section>
        </div>

        <!-- AI Tab -->
        <div class="settings-tab-content" class:active={activeTab === "ai"}>
          <h2 class="settings-page-title">AI</h2>
          <AISettingsTab orgs={data.orgs} />
        </div>

        <!-- Developer Tab -->
        <div class="settings-tab-content" class:active={activeTab === "developer"}>
          <h2 class="settings-page-title">Developer</h2>
          <section class="settings-section">
            <h3 class="settings-subsection-title">API Access Token</h3>
            <p class="settings-tab-intro">
              Use this token to authenticate API requests. Keep it secure and do not share it.
            </p>
            <div class="settings-field">
              <label for="access-token-input">Access Token</label>
              <div class="token-display-group">
                <input
                  id="access-token-input"
                  type="text"
                  readonly
                  class="token-input"
                  value={data.user?.access_token || ""}
                />
                <button class="btn-secondary" onclick={copyToken}>Copy</button>
              </div>
            </div>
            <div class="token-actions">
              <button class="btn-danger" onclick={handleRegenerateToken}> Regenerate Token </button>
              <p class="warning-text">
                Warning: Regenerating will invalidate your current token immediately.
              </p>
            </div>
          </section>

          <a href="/dev/" class="dev-link-card">
            <div class="dev-link-card-icon">
              {@html codeIcon}
            </div>
            <div class="dev-link-card-content">
              <h4>Developer Portal</h4>
              <p>Explore API documentation, authentication, and integration guides.</p>
            </div>
            <div class="dev-link-card-arrow">
              {@html chevronIcon}
            </div>
          </a>
        </div>
      {/if}
    </main>
  </div>

  {#if !data.loading}
  <footer class="settings-footer">
    <div class="settings-footer-content">
      <div class="settings-footer-column">
        <h4>Legal</h4>
        <a href="/privacy/">Privacy Policy</a>
        <a href="/terms/">Terms and Conditions</a>
        <p class="copyright">© histre inc</p>
      </div>
      <div class="settings-footer-column">
        <h4>Contact</h4>
        <a href="mailto:support@hyperclast.com">support@hyperclast.com</a>
        <p class="address">548 Market St #42127<br />San Francisco CA 94104</p>
      </div>
      <div class="settings-footer-column">
        <h4>Learn More</h4>
        <a href="/about/">About Us</a>
        <a href="/dev/">Developer Portal</a>
        {#if pricingEnabled}<a href="/pricing/">Pricing</a>{/if}
      </div>
      <div class="settings-footer-column">
        <h4>Community</h4>
        <a href="https://github.com/hyperclast/workspace/discussions" target="_blank" rel="noopener"
          ><svg class="footer-icon" viewBox="0 0 16 16" fill="currentColor"
            ><path
              d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8Z"
            /></svg
          >GitHub</a
        >
        <a href="https://discord.gg/Tk349dxVWG" target="_blank" rel="noopener"
          ><svg class="footer-icon" viewBox="0 0 16 16" fill="currentColor"
            ><path
              d="M13.545 2.907a13.227 13.227 0 0 0-3.257-1.011.05.05 0 0 0-.052.025c-.141.25-.297.577-.406.833a12.19 12.19 0 0 0-3.658 0 8.258 8.258 0 0 0-.412-.833.051.051 0 0 0-.052-.025c-1.125.194-2.22.534-3.257 1.011a.041.041 0 0 0-.021.018C.356 6.024-.213 9.047.066 12.032c.001.014.01.028.021.037a13.276 13.276 0 0 0 3.995 2.02.05.05 0 0 0 .056-.019c.308-.42.582-.863.818-1.329a.05.05 0 0 0-.01-.059.051.051 0 0 0-.018-.011 8.875 8.875 0 0 1-1.248-.595.05.05 0 0 1-.02-.066.051.051 0 0 1 .015-.019c.084-.063.168-.129.248-.195a.05.05 0 0 1 .051-.007c2.619 1.196 5.454 1.196 8.041 0a.052.052 0 0 1 .053.007c.08.066.164.132.248.195a.051.051 0 0 1-.004.085 8.254 8.254 0 0 1-1.249.594.05.05 0 0 0-.03.03.052.052 0 0 0 .003.041c.24.465.515.909.817 1.329a.05.05 0 0 0 .056.019 13.235 13.235 0 0 0 4.001-2.02.049.049 0 0 0 .021-.037c.334-3.451-.559-6.449-2.366-9.106a.034.034 0 0 0-.02-.019Zm-8.198 7.307c-.789 0-1.438-.724-1.438-1.612 0-.889.637-1.613 1.438-1.613.807 0 1.45.73 1.438 1.613 0 .888-.637 1.612-1.438 1.612Zm5.316 0c-.788 0-1.438-.724-1.438-1.612 0-.889.637-1.613 1.438-1.613.807 0 1.451.73 1.438 1.613 0 .888-.631 1.612-1.438 1.612Z"
            /></svg
          >Discord</a
        >
        <a href="https://www.reddit.com/r/hyperclast/" target="_blank" rel="noopener"
          ><svg class="footer-icon" viewBox="0 0 24 24" fill="currentColor"
            ><path
              d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z"
            /></svg
          >Reddit</a
        >
        <a href="https://x.com/HyperclastHQ" target="_blank" rel="noopener"
          ><svg class="footer-icon" viewBox="0 0 16 16" fill="currentColor"
            ><path
              d="M12.6.75h2.454l-5.36 6.142L16 15.25h-4.937l-3.867-5.07-4.425 5.07H.316l5.733-6.57L0 .75h5.063l3.495 4.633L12.601.75Zm-.86 13.028h1.36L4.323 2.145H2.865l8.875 11.633Z"
            /></svg
          >Twitter</a
        >
        <a href="https://www.youtube.com/@hyperclast" target="_blank" rel="noopener"
          ><svg class="footer-icon" viewBox="0 0 16 16" fill="currentColor"
            ><path
              d="M8.051 1.999h.089c.822.003 4.987.033 6.11.335a2.01 2.01 0 0 1 1.415 1.42c.101.38.172.883.22 1.402l.01.104.022.26.008.104c.065.914.073 1.77.074 1.957v.075c-.001.194-.01 1.108-.082 2.06l-.008.105-.009.104c-.05.572-.124 1.14-.235 1.558a2.007 2.007 0 0 1-1.415 1.42c-1.16.312-5.569.334-6.18.335h-.142c-.309 0-1.587-.006-2.927-.052l-.17-.006-.087-.004-.171-.007-.171-.007c-1.11-.049-2.167-.128-2.654-.26a2.007 2.007 0 0 1-1.415-1.419c-.111-.417-.185-.986-.235-1.558L.09 9.82l-.008-.104A31.4 31.4 0 0 1 0 7.68v-.123c.002-.215.01-.958.064-1.778l.007-.103.003-.052.008-.104.022-.26.01-.104c.048-.519.119-1.023.22-1.402a2.007 2.007 0 0 1 1.415-1.42c.487-.13 1.544-.21 2.654-.26l.17-.007.172-.006.086-.003.171-.007A99.788 99.788 0 0 1 7.858 2h.193ZM6.4 5.209v4.818l4.157-2.408L6.4 5.209Z"
            /></svg
          >YouTube</a
        >
        </div>
    </div>
  </footer>
  {/if}
</div>

<style>
  .settings-page-wrapper {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
  }

  .settings-layout {
    display: flex;
    flex: 1;
  }

  .settings-sidebar {
    width: 220px;
    flex-shrink: 0;
    background: var(--bg-primary);
    border-right: 1px solid var(--border-light);
    padding: 1.5rem 1rem;
  }

  .settings-sidebar-title {
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0 0 1.5rem 0.5rem;
  }

  .settings-nav {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .settings-nav-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.625rem 0.75rem;
    border: none;
    background: transparent;
    color: var(--text-secondary);
    font-size: 0.9rem;
    font-weight: 500;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
    text-align: left;
    width: 100%;
  }

  .settings-nav-item:hover {
    background: rgba(102, 126, 234, 0.08);
    color: var(--text-primary);
  }

  .settings-nav-item.active {
    background: rgba(102, 126, 234, 0.12);
    color: #667eea;
  }

  .settings-nav-item .nav-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
  }

  .settings-nav-item .nav-icon :global(svg) {
    width: 18px;
    height: 18px;
  }

  .settings-main {
    flex: 1;
    background: var(--bg-secondary);
    padding: 2rem 3rem;
  }

  .settings-tab-content {
    max-width: 680px;
  }

  .settings-page-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0 0 1.5rem 0;
  }

  @media (max-width: 768px) {
    .settings-layout {
      flex-direction: column;
    }

    .settings-sidebar {
      width: 100%;
      border-right: none;
      border-bottom: 1px solid var(--border-light);
      padding: 1rem;
    }

    .settings-sidebar-title {
      display: none;
    }

    .settings-nav {
      flex-direction: row;
      gap: 0.5rem;
      overflow-x: auto;
    }

    .settings-nav-item {
      flex-shrink: 0;
      padding: 0.5rem 0.75rem;
    }

    .settings-nav-item .nav-label {
      display: none;
    }

    .settings-main {
      padding: 1.5rem;
    }

    .settings-tab-content {
      max-width: none;
    }
  }
</style>
