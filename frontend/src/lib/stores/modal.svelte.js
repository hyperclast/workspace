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
  orgName: "",
});

export function getShareProjectState() {
  return shareProjectState;
}

export function openShareProject(options) {
  // Mutate existing object instead of reassigning
  shareProjectState.projectId = options.projectId || "";
  shareProjectState.projectName = options.projectName || "";
  shareProjectState.orgName = options.orgName || "";
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
  pageContent: "",
  onchanged: () => {},
});

export function getChangePageTypeState() {
  return changePageTypeState;
}

export function openChangePageType(options = {}) {
  changePageTypeState.pageId = options.pageId || "";
  changePageTypeState.pageTitle = options.pageTitle || "";
  changePageTypeState.currentType = options.currentType || "md";
  changePageTypeState.pageContent = options.pageContent ?? "";
  changePageTypeState.onchanged = options.onchanged || (() => {});
  changePageTypeState.open = true;
}

export function closeChangePageType() {
  changePageTypeState.open = false;
}

let commandPaletteState = $state({
  open: false,
  projects: [],
  currentPageId: null,
  currentProjectId: null,
  onselect: () => {},
});

export function getCommandPaletteState() {
  return commandPaletteState;
}

export function openCommandPalette(options = {}) {
  commandPaletteState.projects = options.projects || [];
  commandPaletteState.currentPageId = options.currentPageId || null;
  commandPaletteState.currentProjectId = options.currentProjectId || null;
  commandPaletteState.onselect = options.onselect || (() => {});
  commandPaletteState.open = true;
}

export function closeCommandPalette() {
  commandPaletteState.open = false;
}

let readonlyLinkState = $state({
  open: false,
  pageExternalId: "",
  pageTitle: "",
  accessCode: "",
  onremove: () => {},
});

export function getReadonlyLinkState() {
  return readonlyLinkState;
}

export function openReadonlyLink(options = {}) {
  readonlyLinkState.pageExternalId = options.pageExternalId || "";
  readonlyLinkState.pageTitle = options.pageTitle || "";
  readonlyLinkState.accessCode = options.accessCode || "";
  readonlyLinkState.onremove = options.onremove || (() => {});
  readonlyLinkState.open = true;
}

export function closeReadonlyLink() {
  readonlyLinkState.open = false;
}

let sharePageState = $state({
  open: false,
  pageId: "",
  pageTitle: "",
  onAccessCodeChange: () => {},
});

export function getSharePageState() {
  return sharePageState;
}

export function openSharePage(options = {}) {
  sharePageState.pageId = options.pageId || "";
  sharePageState.pageTitle = options.pageTitle || "";
  sharePageState.onAccessCodeChange = options.onAccessCodeChange || (() => {});
  sharePageState.open = true;
}

export function closeSharePage() {
  sharePageState.open = false;
}
