<script>
  import ConfirmModal from './ConfirmModal.svelte';
  import PromptModal from './PromptModal.svelte';
  import ShareProjectModal from './ShareProjectModal.svelte';
  import SharePageModal from './SharePageModal.svelte';
  import CreateProjectModal from './CreateProjectModal.svelte';
  import { getConfirmState, getPromptState, getShareProjectState, getSharePageState, getCreateProjectState } from '../stores/modal.svelte.js';

  // Get reactive state references directly (not $derived, which would be read-only)
  const confirmState = getConfirmState();
  const promptState = getPromptState();
  const shareProjectState = getShareProjectState();
  const sharePageState = getSharePageState();
  const createProjectState = getCreateProjectState();
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

<SharePageModal
  bind:open={sharePageState.open}
  pageId={sharePageState.pageId}
  pageTitle={sharePageState.pageTitle}
/>

<CreateProjectModal
  bind:open={createProjectState.open}
  oncreated={createProjectState.oncreated}
/>
