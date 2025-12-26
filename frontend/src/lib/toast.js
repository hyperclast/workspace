import { mount } from 'svelte';
import Toast from './components/Toast.svelte';
import { showToast as _showToast } from './stores/toast.svelte.js';

let mounted = false;

export function initToast() {
  if (mounted) return;
  mounted = true;

  const container = document.createElement('div');
  container.id = 'svelte-toast-root';
  document.body.appendChild(container);

  mount(Toast, { target: container });
}

export function showToast(message, type = 'success', duration = 5000) {
  initToast();
  _showToast(message, type, duration);
}
