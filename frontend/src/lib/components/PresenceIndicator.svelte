<script>
  import { getUsers, getShowPopover } from "../stores/presence.svelte.js";

  const users = $derived(getUsers());
  const showPopover = $derived(getShowPopover());

  const MAX_VISIBLE = 3;
  const visibleUsers = $derived(users.slice(0, MAX_VISIBLE));
  const overflowCount = $derived(Math.max(0, users.length - MAX_VISIBLE));

  function initial(name) {
    const trimmed = (name || "").trim();
    return trimmed ? trimmed.charAt(0).toUpperCase() : "?";
  }

  // When gravatar 404s the img errors out — hide it so the initial behind shows.
  function hideOnError(e) {
    e.currentTarget.style.display = "none";
  }
</script>

{#if users.length > 0}
  <div class="presence-cluster" id="user-count" data-count={users.length}>
    {#each visibleUsers as user, i (user.clientId)}
      <span
        class="presence-avatar"
        class:is-current={user.isCurrent}
        style="background-color: {user.color}; z-index: {MAX_VISIBLE - i};"
        title={user.name}
      >
        {initial(user.name)}
        {#if user.picture}
          <img
            class="presence-avatar-img"
            src={user.picture}
            alt=""
            onerror={hideOnError}
          />
        {/if}
      </span>
    {/each}
    {#if overflowCount > 0}
      <span class="presence-avatar presence-overflow" style="z-index: 0;" title="{overflowCount} more">
        +{overflowCount}
      </span>
    {/if}
  </div>
  <div
    id="presence-popover"
    class="presence-popover"
    style="display: {showPopover ? 'block' : 'none'};"
  >
    <div class="presence-popover-header">
      {users.length === 1 ? "1 user editing" : `${users.length} users editing`}
    </div>
    <div id="presence-list" class="presence-list">
      {#each users as user (user.clientId)}
        <div class="presence-user">
          <span class="presence-user-avatar" style="background-color: {user.color};">
            {initial(user.name)}
            {#if user.picture}
              <img
                class="presence-avatar-img"
                src={user.picture}
                alt=""
                onerror={hideOnError}
              />
            {/if}
          </span>
          <span class="presence-user-name">
            {user.name}{user.isCurrent ? " (you)" : ""}
          </span>
        </div>
      {/each}
    </div>
  </div>
{/if}
