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

  // Deduplicate: if an identical toast is already showing, return its ID
  const existing = toasts.find((t) => t.message === message && t.type === type);
  if (existing) return existing.id;

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

  return id;
}

export function removeToast(id) {
  toasts = toasts.filter((t) => t.id !== id);
}
