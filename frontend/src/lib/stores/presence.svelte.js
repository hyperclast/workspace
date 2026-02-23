/**
 * Reactive state for the presence indicator.
 * Using a .svelte.js module so $state is available outside components.
 */

let users = $state([]);
let showPopover = $state(false);

export function getUsers() {
  return users;
}

export function setUsers(newUsers) {
  users = newUsers;
}

export function getShowPopover() {
  return showPopover;
}

export function setShowPopover(value) {
  showPopover = value;
}
