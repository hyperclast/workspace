import { mount } from "svelte";
import Toast from "./components/Toast.svelte";
import { showToast as _showToast } from "./stores/toast.svelte.js";

let mounted = false;

export function initToast() {
  // Check if container already exists on body
  let container = document.getElementById("svelte-toast-root");
  if (mounted && container) return;

  // Create container if it doesn't exist
  if (!container) {
    container = document.createElement("div");
    container.id = "svelte-toast-root";
    document.body.appendChild(container);
  } else {
    container.innerHTML = "";
  }

  mount(Toast, { target: container });
  mounted = true;
}

export function showToast(message, type = "success", options = {}) {
  initToast();
  _showToast(message, type, options);
}
