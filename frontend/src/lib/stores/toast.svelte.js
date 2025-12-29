let toasts = $state([]);
let nextId = 0;

export function getToasts() {
  return toasts;
}

export function showToast(message, type = "success", duration = 5000) {
  const id = nextId++;
  toasts.push({ id, message, type });

  if (type !== "error") {
    setTimeout(() => {
      removeToast(id);
    }, duration);
  }
}

export function removeToast(id) {
  toasts = toasts.filter((t) => t.id !== id);
}
