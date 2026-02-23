<script>
  import {
    getStatus,
    getShowPopover,
  } from "../stores/collabStatus.svelte.js";

  const STATUS_CONFIG = {
    connecting: {
      icon: "\u25CC",
      header: "Connecting",
      text: "Establishing connection to sync server...",
      class: "connecting",
    },
    connected: {
      icon: "\u25CF",
      header: "Connected",
      text: "Changes sync instantly with other editors.",
      class: "connected",
    },
    offline: {
      icon: "\u25CF",
      header: "Offline",
      text: "Changes are saved locally. They will sync when you reconnect.",
      class: "offline",
    },
    denied: {
      icon: "\u2298",
      header: "Unavailable",
      text: "Real-time collaboration is not available for this page.",
      class: "denied",
    },
    error: {
      icon: "!",
      header: "Connection Lost",
      text: "Attempting to reconnect...",
      class: "error",
    },
    unauthorized: {
      icon: "\u25CB",
      header: "Logged Out",
      text: "Please log in to continue editing.",
      class: "unauthorized",
    },
  };

  const status = $derived(getStatus());
  const showPopover = $derived(getShowPopover());
  const config = $derived(STATUS_CONFIG[status] || STATUS_CONFIG.offline);
</script>

<span id="collab-status" class="collab-status {config.class}"
  >{config.icon}</span
>
<div
  id="collab-popover"
  class="indicator-popover collab-popover"
  style="display: {showPopover ? 'block' : 'none'};"
>
  <div id="collab-popover-header" class="indicator-popover-header">{config.header}</div>
  <div id="collab-popover-text" class="indicator-popover-text">{config.text}</div>
</div>
