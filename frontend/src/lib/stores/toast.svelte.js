let toasts = $state([]);
let nextId = 0;

export function getToasts() {
  return toasts;
}

export function showToast(message, type = "success", options = {}) {
  // Support legacy duration parameter: showToast(msg, type, 5000)
  if (typeof options === "number") {
    options = { duration: options };
  }

  const id = nextId++;
  const duration = options.duration ?? (type === "error" ? 0 : 5000);

  toasts.push({
    id,
    message,
    type,
    action: options.action || null, // { label: string, onClick: () => void }
  });

  if (duration > 0) {
    setTimeout(() => {
      removeToast(id);
    }, duration);
  }
}

export function removeToast(id) {
  toasts = toasts.filter((t) => t.id !== id);
}
