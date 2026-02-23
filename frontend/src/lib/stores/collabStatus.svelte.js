/**
 * Reactive state for the collab status indicator.
 * Using a .svelte.js module so $state is available outside components.
 */

let status = $state("connecting");
let showPopover = $state(false);

export function getStatus() {
  return status;
}

export function setStatus(newStatus) {
  status = newStatus;
}

export function getShowPopover() {
  return showPopover;
}

export function setShowPopover(value) {
  showPopover = value;
}
