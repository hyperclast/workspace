let confirmState = $state({
  open: false,
  title: "Confirm",
  message: "",
  description: "",
  confirmText: "Confirm",
  cancelText: "Cancel",
  danger: false,
  onconfirm: () => {},
  oncancel: () => {},
});

export function getConfirmState() {
  return confirmState;
}

export function openConfirm(options) {
  return new Promise((resolve) => {
    // Mutate existing object instead of reassigning
    confirmState.title = options.title || "Confirm";
    confirmState.message = options.message || "";
    confirmState.description = options.description || "";
    confirmState.confirmText = options.confirmText || "Confirm";
    confirmState.cancelText = options.cancelText || "Cancel";
    confirmState.danger = options.danger || false;
    confirmState.onconfirm = () => resolve(true);
    confirmState.oncancel = () => resolve(false);
    confirmState.open = true;
  });
}

export function closeConfirm() {
  confirmState.open = false;
}

let promptState = $state({
  open: false,
  title: "Enter value",
  label: "",
  placeholder: "",
  value: "",
  confirmText: "Save",
  cancelText: "Cancel",
  maxlength: 255,
  required: true,
  validate: null,
  onconfirm: () => {},
  oncancel: () => {},
});

export function getPromptState() {
  return promptState;
}

export function openPrompt(options) {
  return new Promise((resolve) => {
    // Mutate existing object instead of reassigning
    promptState.title = options.title || "Enter value";
    promptState.label = options.label || "";
    promptState.placeholder = options.placeholder || "";
    promptState.value = options.value || "";
    promptState.confirmText = options.confirmText || "Save";
    promptState.cancelText = options.cancelText || "Cancel";
    promptState.maxlength = options.maxlength || 255;
    promptState.required = options.required !== false;
    promptState.validate = options.validate || null;
    promptState.onconfirm = (value) => resolve(value);
    promptState.oncancel = () => resolve(null);
    promptState.open = true;
  });
}

export function closePrompt() {
  promptState.open = false;
}

let shareProjectState = $state({
  open: false,
  projectId: "",
  projectName: "",
});

export function getShareProjectState() {
  return shareProjectState;
}

export function openShareProject(options) {
  // Mutate existing object instead of reassigning
  shareProjectState.projectId = options.projectId || "";
  shareProjectState.projectName = options.projectName || "";
  shareProjectState.open = true;
}

export function closeShareProject() {
  shareProjectState.open = false;
}

let createProjectState = $state({
  open: false,
  oncreated: () => {},
});

export function getCreateProjectState() {
  return createProjectState;
}

export function openCreateProject(options = {}) {
  createProjectState.oncreated = options.oncreated || (() => {});
  createProjectState.open = true;
}

export function closeCreateProject() {
  createProjectState.open = false;
}

let newPageState = $state({
  open: false,
  projectId: "",
  pages: [],
  oncreated: () => {},
});

export function getNewPageState() {
  return newPageState;
}

export function openNewPage(options = {}) {
  newPageState.projectId = options.projectId || "";
  newPageState.pages = options.pages || [];
  newPageState.oncreated = options.oncreated || (() => {});
  newPageState.open = true;
}

export function closeNewPage() {
  newPageState.open = false;
}

let changePageTypeState = $state({
  open: false,
  pageId: "",
  pageTitle: "",
  currentType: "md",
  onchanged: () => {},
});

export function getChangePageTypeState() {
  return changePageTypeState;
}

export function openChangePageType(options = {}) {
  changePageTypeState.pageId = options.pageId || "";
  changePageTypeState.pageTitle = options.pageTitle || "";
  changePageTypeState.currentType = options.currentType || "md";
  changePageTypeState.onchanged = options.onchanged || (() => {});
  changePageTypeState.open = true;
}

export function closeChangePageType() {
  changePageTypeState.open = false;
}
