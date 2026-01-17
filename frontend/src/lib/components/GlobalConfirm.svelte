<script>
  import ConfirmModal from './ConfirmModal.svelte';
  import PromptModal from './PromptModal.svelte';
  import ShareProjectModal from './ShareProjectModal.svelte';
  import SharePageModal from './SharePageModal.svelte';
  import CreateProjectModal from './CreateProjectModal.svelte';
  import NewPageModal from './NewPageModal.svelte';
  import ChangePageTypeModal from './ChangePageTypeModal.svelte';
  import CommandPalette from './CommandPalette.svelte';
  import ReadOnlyLinkModal from './ReadOnlyLinkModal.svelte';
  import { getConfirmState, getPromptState, getShareProjectState, getCreateProjectState, getNewPageState, getChangePageTypeState, getCommandPaletteState, getReadonlyLinkState, getSharePageState } from '../stores/modal.svelte.js';

  const confirmState = getConfirmState();
  const promptState = getPromptState();
  const shareProjectState = getShareProjectState();
  const sharePageState = getSharePageState();
  const createProjectState = getCreateProjectState();
  const newPageState = getNewPageState();
  const changePageTypeState = getChangePageTypeState();
  const commandPaletteState = getCommandPaletteState();
  const readonlyLinkState = getReadonlyLinkState();
</script>

<ConfirmModal
  bind:open={confirmState.open}
  title={confirmState.title}
  message={confirmState.message}
  description={confirmState.description}
  confirmText={confirmState.confirmText}
  cancelText={confirmState.cancelText}
  danger={confirmState.danger}
  onconfirm={confirmState.onconfirm}
  oncancel={confirmState.oncancel}
/>

<PromptModal
  bind:open={promptState.open}
  bind:value={promptState.value}
  title={promptState.title}
  label={promptState.label}
  placeholder={promptState.placeholder}
  confirmText={promptState.confirmText}
  cancelText={promptState.cancelText}
  maxlength={promptState.maxlength}
  required={promptState.required}
  validate={promptState.validate}
  onconfirm={promptState.onconfirm}
  oncancel={promptState.oncancel}
/>

<ShareProjectModal
  bind:open={shareProjectState.open}
  projectId={shareProjectState.projectId}
  projectName={shareProjectState.projectName}
  orgName={shareProjectState.orgName}
/>

<CreateProjectModal
  bind:open={createProjectState.open}
  oncreated={createProjectState.oncreated}
/>

<NewPageModal
  bind:open={newPageState.open}
  projectId={newPageState.projectId}
  pages={newPageState.pages}
  oncreated={newPageState.oncreated}
/>

<ChangePageTypeModal
  bind:open={changePageTypeState.open}
  pageId={changePageTypeState.pageId}
  pageTitle={changePageTypeState.pageTitle}
  currentType={changePageTypeState.currentType}
  pageContent={changePageTypeState.pageContent}
  onchanged={changePageTypeState.onchanged}
/>

<CommandPalette
  bind:open={commandPaletteState.open}
  projects={commandPaletteState.projects}
  currentPageId={commandPaletteState.currentPageId}
  currentProjectId={commandPaletteState.currentProjectId}
  onselect={commandPaletteState.onselect}
/>

<ReadOnlyLinkModal
  bind:open={readonlyLinkState.open}
  pageExternalId={readonlyLinkState.pageExternalId}
  pageTitle={readonlyLinkState.pageTitle}
  accessCode={readonlyLinkState.accessCode}
  onremove={readonlyLinkState.onremove}
/>

<SharePageModal
  bind:open={sharePageState.open}
  pageId={sharePageState.pageId}
  pageTitle={sharePageState.pageTitle}
  onAccessCodeChange={sharePageState.onAccessCodeChange}
/>
