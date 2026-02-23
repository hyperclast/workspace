<script>
  import { getUsers, getShowPopover } from "../stores/presence.svelte.js";

  const users = $derived(getUsers());
  const showPopover = $derived(getShowPopover());
</script>

<span
  id="user-count"
  data-count={users.length}
>{users.length === 1 ? "1 user editing" : `${users.length} users editing`}</span>
<div
  id="presence-popover"
  class="presence-popover"
  style="display: {showPopover ? 'block' : 'none'};"
>
  <div class="presence-popover-header">Users editing</div>
  <div id="presence-list" class="presence-list">
    {#each users as user (user.clientId)}
      <div class="presence-user">
        <div class="presence-user-color" style="background-color: {user.color};"></div>
        <span>{user.name}</span>
      </div>
    {/each}
  </div>
</div>
