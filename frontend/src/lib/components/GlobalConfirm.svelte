<script>
  import ConfirmModal from './ConfirmModal.svelte';
  import PromptModal from './PromptModal.svelte';
  import ShareProjectModal from './ShareProjectModal.svelte';
  import CreateProjectModal from './CreateProjectModal.svelte';
  import NewPageModal from './NewPageModal.svelte';
  import { getConfirmState, getPromptState, getShareProjectState, getCreateProjectState, getNewPageState } from '../stores/modal.svelte.js';

  const confirmState = getConfirmState();
  const promptState = getPromptState();
  const shareProjectState = getShareProjectState();
  const createProjectState = getCreateProjectState();
  const newPageState = getNewPageState();
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
