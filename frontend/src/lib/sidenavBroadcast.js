/**
 * Cross-tab synchronization for sidenav using BroadcastChannel API.
 * When pages/projects are created or deleted in one tab, other tabs
 * are notified to refresh their sidenav.
 */

const CHANNEL_NAME = "sidenav-sync";

let channel = null;
let refreshCallback = null;

/**
 * Initialize the broadcast channel and set up listener.
 * @param {Function} onRefreshNeeded - Called when another tab signals a refresh is needed
 */
export function initSidenavBroadcast(onRefreshNeeded) {
  if (typeof BroadcastChannel === "undefined") {
    // BroadcastChannel not supported (e.g., older browsers)
    console.warn("BroadcastChannel not supported - cross-tab sync disabled");
    return;
  }

  refreshCallback = onRefreshNeeded;
  channel = new BroadcastChannel(CHANNEL_NAME);

  channel.onmessage = (event) => {
    if (event.data?.type === "sidenav-changed" && refreshCallback) {
      refreshCallback();
    }
  };
}

/**
 * Broadcast that the sidenav data has changed (page/project created/deleted).
 * Other tabs listening will refresh their sidenav.
 */
export function broadcastSidenavChanged() {
  if (channel) {
    channel.postMessage({ type: "sidenav-changed" });
  }
}

/**
 * Clean up the broadcast channel.
 */
export function closeSidenavBroadcast() {
  if (channel) {
    channel.close();
    channel = null;
  }
}
