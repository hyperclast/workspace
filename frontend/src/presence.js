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
    userCountSpan.setAttribute("data-count", count);

    // Update presence list using DOM APIs to prevent XSS via user names/colors
    presenceList.innerHTML = "";
    for (const user of users) {
      const userDiv = document.createElement("div");
      userDiv.className = "presence-user";

      const colorDiv = document.createElement("div");
      colorDiv.className = "presence-user-color";
      colorDiv.style.backgroundColor = user.color;

      const nameSpan = document.createElement("span");
      nameSpan.textContent = user.name;

      userDiv.appendChild(colorDiv);
      userDiv.appendChild(nameSpan);
      presenceList.appendChild(userDiv);
    }
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

  // Click to open (for touch devices where hover doesn't work)
  presenceIndicator.addEventListener("click", () => {
    clearTimeout(hideTimeout);
    presencePopover.style.display = "block";
  });

  // Close on click outside
  document.addEventListener("click", (e) => {
    if (!presenceIndicator.contains(e.target)) {
      clearTimeout(hideTimeout);
      presencePopover.style.display = "none";
    }
  });

  // Return cleanup function
  return () => {
    awareness.off("change", updatePresenceUI);
    clearTimeout(hideTimeout);
  };
}
