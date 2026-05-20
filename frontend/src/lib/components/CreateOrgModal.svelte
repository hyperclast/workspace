<script>
  import Modal from "./Modal.svelte";
  import { createOrg } from "../../api.js";
  import { showToast } from "../toast.js";

  let { open = $bindable(false), oncreated = () => {} } = $props();

  let name = $state("");
  let loading = $state(false);
  let error = $state("");
  let inputEl = $state(null);

  let trimmed = $derived(name.trim());
  let valid = $derived(trimmed.length > 0 && trimmed.length <= 255);

  $effect(() => {
    if (open) {
      name = "";
      error = "";
      loading = false;
      setTimeout(() => {
        inputEl?.focus();
      }, 50);
    }
  });

  async function handleCreate() {
    if (!valid || loading) return;
    error = "";
    loading = true;
    try {
      const org = await createOrg(trimmed);
      open = false;
      oncreated(org);
      showToast("Organization created");
    } catch (e) {
      error = e?.message || "Failed to create organization";
    } finally {
      loading = false;
    }
  }

  function handleKeydown(e) {
    if (e.key === "Enter" && !loading) {
      handleCreate();
    }
  }
</script>

<Modal bind:open title="New organization" size="sm">
  <div class="modal-field">
    <label for="org-name-input">Organization name</label>
    <input
      bind:this={inputEl}
      bind:value={name}
      type="text"
      id="org-name-input"
      placeholder="My Organization"
      maxlength="255"
      disabled={loading}
      onkeydown={handleKeydown}
    />
    <p class="field-hint">
      An organization groups projects and members. You can invite others later.
    </p>
  </div>

  {#if error}
    <div class="modal-error-message">{error}</div>
  {/if}

  {#snippet footer()}
    <button class="modal-btn-secondary" onclick={() => (open = false)} disabled={loading}>
      Cancel
    </button>
    <button class="modal-btn-primary" onclick={handleCreate} disabled={loading || !valid}>
      {loading ? "Creating..." : "Create organization"}
    </button>
  {/snippet}
</Modal>

<style>
  .modal-field {
    margin-bottom: 1rem;
  }

  .modal-field label {
    display: block;
    margin-bottom: 0.375rem;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-primary);
  }

  .modal-field input {
    width: 100%;
    padding: 0.625rem 0.75rem;
    border: 1px solid var(--border-light);
    border-radius: 6px;
    font-size: 0.9rem;
    background: var(--bg-primary);
    color: var(--text-primary);
    transition: border-color 0.15s, box-shadow 0.15s;
  }

  .modal-field input:focus {
    outline: none;
    border-color: var(--accent-color);
    box-shadow: 0 0 0 3px rgba(35, 131, 226, 0.1);
  }

  .modal-field input:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .field-hint {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-top: 0.375rem;
    line-height: 1.4;
  }

  .modal-error-message {
    padding: 0.625rem 0.75rem;
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 6px;
    color: #dc2626;
    font-size: 0.875rem;
    margin-top: 0.5rem;
  }
</style>
