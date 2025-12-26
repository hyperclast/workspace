/**
 * Presence indicators UI management
 * Shows who's currently editing the document
 */

/**
 * Setup presence UI and listen to awareness changes
 * @param {Object} awareness - Yjs awareness object
 */
export function setupPresenceUI(awareness) {
  const presenceIndicator = document.getElementById("presence-indicator");
  const presencePopover = document.getElementById("presence-popover");
  const userCountSpan = document.getElementById("user-count");
  const presenceList = document.getElementById("presence-list");

  // Update presence UI when awareness changes
  function updatePresenceUI() {
    const states = awareness.getStates();
    const users = [];

    // Collect all users from awareness states
    states.forEach((state, clientId) => {
      if (state.user) {
        users.push({
          clientId,
          name: state.user.name || "Anonymous",
          color: state.user.color || "#999",
        });
      }
    });

    // Update user count
    const count = users.length;
    userCountSpan.textContent = count === 1 ? "1 user editing" : `${count} users editing`;

    // Update presence list
    presenceList.innerHTML = users
      .map(
        (user) => `
      <div class="presence-user">
        <div class="presence-user-color" style="background-color: ${user.color}"></div>
        <span>${user.name}</span>
      </div>
    `
      )
      .join("");
  }

  // Listen to awareness changes
  awareness.on("change", updatePresenceUI);

  // Initial update
  updatePresenceUI();

  // Show/hide popover on hover
  let hideTimeout;

  presenceIndicator.addEventListener("mouseenter", () => {
    clearTimeout(hideTimeout);
    presencePopover.style.display = "block";
  });

  presenceIndicator.addEventListener("mouseleave", () => {
    hideTimeout = setTimeout(() => {
      presencePopover.style.display = "none";
    }, 300);
  });

  presencePopover.addEventListener("mouseenter", () => {
    clearTimeout(hideTimeout);
  });

  presencePopover.addEventListener("mouseleave", () => {
    hideTimeout = setTimeout(() => {
      presencePopover.style.display = "none";
    }, 300);
  });

  // Return cleanup function
  return () => {
    awareness.off("change", updatePresenceUI);
    clearTimeout(hideTimeout);
  };
}
