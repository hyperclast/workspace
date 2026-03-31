<script>
  import { onMount, onDestroy, tick } from "svelte";
  import { flip } from "svelte/animate";
  import { slide } from "svelte/transition";
  import { PERSONAS, PERSONA_SPRITE_URL } from "../../personaImages.js";
  import { formatCommentBody } from "../../utils/formatComment.js";
  import { resolveAnchorRange, buildSuggestionChange } from "../../utils/applySuggestion.js";
  import { registerTabHandler, registerPageChangeHandler, getState, openSidebar, setActiveTab } from "../../stores/sidebar.svelte.js";
  import {
    fetchComments as apiFetchComments,
    createComment as apiCreateComment,
    deleteComment as apiDeleteComment,
    resolveComment as apiResolveComment,
    unresolveComment as apiUnresolveComment,
    triggerAIReview as apiTriggerAIReview,
    createRewindCheckpoint as apiCreateRewindCheckpoint,
    generateCommentEdit as apiGenerateCommentEdit,
  } from "../../../api.js";
  import { isDemoMode } from "../../../demo/index.js";
  import {
    fetchComments as demoFetchComments,
    createComment as demoCreateComment,
    deleteComment as demoDeleteComment,
    resolveComment as demoResolveComment,
    unresolveComment as demoUnresolveComment,
    triggerAIReview as demoTriggerAIReview,
    createRewindCheckpoint as demoCreateRewindCheckpoint,
    generateCommentEdit as demoGenerateCommentEdit,
  } from "../../../demo/demoApi.js";
  import {
    resolveCommentAnchors,
    updateCommentHighlights,
    setActiveCommentHighlight,
  } from "../../../commentAnchors.js";
  import { commentHighlightField } from "../../../decorateComments.js";
  import { EditorView } from "@codemirror/view";
  import {
    subscribe as subscribeRewind,
    getState as getRewindState,
    exitRewindMode,
  } from "../../../rewind/index.js";
  import { getUserInfo } from "../../../config.js";
  import { showToast } from "../../toast.js";

  function getApi() {
    return isDemoMode()
      ? { fetchComments: demoFetchComments, createComment: demoCreateComment, deleteComment: demoDeleteComment, resolveComment: demoResolveComment, unresolveComment: demoUnresolveComment, triggerAIReview: demoTriggerAIReview, createRewindCheckpoint: demoCreateRewindCheckpoint, generateCommentEdit: demoGenerateCommentEdit }
      : { fetchComments: apiFetchComments, createComment: apiCreateComment, deleteComment: apiDeleteComment, resolveComment: apiResolveComment, unresolveComment: apiUnresolveComment, triggerAIReview: apiTriggerAIReview, createRewindCheckpoint: apiCreateRewindCheckpoint, generateCommentEdit: apiGenerateCommentEdit };
  }

  let comments = $state([]);
  let currentPageId = $state(null);
  let currentPageRole = $state(null); // "admin", "editor", "viewer", or null
  let loading = $state(false);
  let replyingTo = $state(null); // external_id of comment being replied to
  let pageCommentBody = $state("");
  let replyBody = $state("");
  let applyingComment = $state(null);

  async function startReply(commentId) {
    if (replyingTo === commentId) {
      replyingTo = null;
      return;
    }
    replyingTo = commentId;
    replyBody = "";
    await tick();
    document.querySelector(".comment-reply-input .comment-textarea")?.focus();
  }

  let commentsUpdatedHandler = null;
  let aiReviewCompleteHandler = null;
  let pendingPersonas = $state(new Set());
  let pendingSelections = {};  // { [persona]: boolean } — tracks whether each pending review is selection-scoped
  let hasEditorSelection = $state(false);
  let isRewindMode = $state(false);
  let unsubscribeRewind = null;
  let docChangeHandler = null;
  let docChangeTimer = null;
  let activeCommentId = $state(null);
  let showNewComment = $state(false);
  let commentFocusedHandler = null;
  let collabStatusHandler = null;
  let resolveRetryTimer = null;

  const sidebarState = getState();

  function resolveAndHighlight() {
    const view = window.editorView;
    const ydoc = window.ydoc;
    const ytext = window.ytext;
    if (!view || !currentPageId) return;

    const allRanges = resolveCommentAnchors(comments, currentPageId, view, ydoc, ytext);
    // Filter out resolved comment bars when hidden
    const ranges = showResolved
      ? allRanges
      : allRanges.filter((r) => {
          const c = comments.find((cm) => cm.external_id === r.commentId);
          return c && !c.is_resolved;
        });
    updateCommentHighlights(view, ranges);

    // Sort comments by document position (anchored comments first, then unanchored)
    const posMap = new Map();
    for (const r of ranges) {
      posMap.set(r.commentId, r.from);
    }
    comments = [...comments].sort((a, b) => {
      const posA = posMap.get(a.external_id);
      const posB = posMap.get(b.external_id);
      if (posA == null && posB == null) return 0;
      if (posA == null) return 1;
      if (posB == null) return -1;
      return posA - posB;
    });
  }

  /**
   * Schedule retries for resolveAndHighlight.
   *
   * During page load the editor is created twice: first with REST content,
   * then replaced by upgradeEditorToCollaborative() after Yjs syncs.
   * The first editor is destroyed, wiping any highlights applied to it.
   * Retries ensure highlights are re-applied to the final editor.
   */
  function scheduleResolveRetry(attemptsLeft) {
    if (resolveRetryTimer) clearTimeout(resolveRetryTimer);
    if (attemptsLeft <= 0) return;

    resolveRetryTimer = setTimeout(() => {
      resolveRetryTimer = null;
      if (!comments.length) return;
      if (!comments.some((c) => !c.parent_id && (c.anchor_from_b64 || c.anchor_text))) return;
      resolveAndHighlight();
      scheduleResolveRetry(attemptsLeft - 1);
    }, 500);
  }

  let loadCommentsInFlight = false;

  async function loadComments() {
    if (!currentPageId) {
      comments = [];
      updateCommentHighlights(window.editorView, []);
      return;
    }

    // Skip if already loading (prevents WebSocket-triggered reload from
    // racing with an in-progress handleReply → loadComments chain).
    if (loadCommentsInFlight) return;
    loadCommentsInFlight = true;

    // Only show loading spinner on initial load, not on refreshes
    const isInitial = comments.length === 0;
    if (isInitial) loading = true;
    try {
      const { fetchComments } = getApi();
      const data = await fetchComments(currentPageId);
      comments = data.items || [];
      resolveAndHighlight();
      // Always retry — the editor may be replaced by the collab upgrade later,
      // wiping highlights applied to the initial REST-content editor.
      if (comments.some((c) => !c.parent_id && (c.anchor_from_b64 || c.anchor_text))) {
        scheduleResolveRetry(10);
      }
    } catch (e) {
      console.error("Error fetching comments:", e);
      comments = [];
    }
    if (isInitial) loading = false;
    loadCommentsInFlight = false;
  }

  async function handleCreatePageComment() {
    if (!pageCommentBody.trim() || !currentPageId) return;

    try {
      const { createComment } = getApi();
      await createComment(currentPageId, {
        body: pageCommentBody.trim(),
        parent_id: null,
      });
      pageCommentBody = "";
      showNewComment = false;
      await loadComments();
    } catch (e) {
      console.error("Error creating page comment:", e);
      showToast("Couldn't post your comment at this time.", "error");
    }
  }

  async function handleReply(parentId) {
    if (!replyBody.trim() || !currentPageId) return;

    try {
      const { createComment } = getApi();
      await createComment(currentPageId, {
        body: replyBody.trim(),
        parent_id: parentId,
      });
      replyBody = "";
      replyingTo = null;

      await loadComments();
    } catch (e) {
      console.error("Error creating reply:", e);
      showToast("Couldn't post your reply at this time.", "error");
    }
  }

  let confirmingDelete = $state(null); // external_id of comment pending delete confirmation

  async function handleDelete(commentId) {
    if (!currentPageId) return;
    if (confirmingDelete !== commentId) {
      // First click — enter confirmation state
      confirmingDelete = commentId;
      return;
    }
    // Second click — actually delete
    confirmingDelete = null;
    try {
      const { deleteComment } = getApi();
      await deleteComment(currentPageId, commentId);
      await loadComments();
    } catch (e) {
      console.error("Error deleting comment:", e);
      showToast("Couldn't delete the comment at this time.", "error");
    }
  }

  function cancelDelete() {
    confirmingDelete = null;
  }

  // --- Resolve/unresolve ---

  let showResolved = $state(localStorage.getItem("comments-show-resolved") === "true");

  function getResolvedCount() {
    return comments.filter((c) => !c.parent_id && c.is_resolved).length;
  }

  function getVisibleComments() {
    if (showResolved) return comments;
    return comments.filter((c) => !c.is_resolved);
  }

  function toggleShowResolved() {
    showResolved = !showResolved;
    localStorage.setItem("comments-show-resolved", showResolved);
    resolveAndHighlight();
  }

  async function handleResolve(commentId) {
    if (!currentPageId) return;
    try {
      const { resolveComment } = getApi();
      await resolveComment(currentPageId, commentId);
      await loadComments();
    } catch (e) {
      console.error("Error resolving comment:", e);
      if (e.status === 403) {
        showToast("You need edit access to resolve discussions.", "error");
      } else {
        showToast("Couldn't resolve the discussion at this time.", "error");
      }
    }
  }

  async function handleUnresolve(commentId) {
    if (!currentPageId) return;
    try {
      const { unresolveComment } = getApi();
      await unresolveComment(currentPageId, commentId);
      await loadComments();
    } catch (e) {
      console.error("Error unresolving comment:", e);
      if (e.status === 403) {
        showToast("You need edit access to unresolve discussions.", "error");
      } else {
        showToast("Couldn't unresolve the discussion at this time.", "error");
      }
    }
  }

  const _inflight = new Set(); // synchronous guard — $state batching can't be trusted for dedup
  async function handleTriggerAIReview(persona) {
    if (!currentPageId || _inflight.has(persona)) return;

    // Capture editor selection at click time
    let selectionText = "";
    const view = window.editorView;
    if (view) {
      const sel = view.state.selection.main;
      if (sel.from !== sel.to) {
        selectionText = view.state.doc.sliceString(sel.from, sel.to);
      }
    }

    _inflight.add(persona);
    pendingPersonas = new Set([...pendingPersonas, persona]);
    pendingSelections[persona] = !!selectionText;
    try {
      const { triggerAIReview } = getApi();
      await triggerAIReview(currentPageId, persona, selectionText || undefined);
      const personaName = persona.charAt(0).toUpperCase() + persona.slice(1);
      const scope = selectionText ? "selection" : "page";
      showToast(`${personaName} is reviewing your ${scope}...`);
      // Comments will arrive via WebSocket commentsUpdated event
    } catch (e) {
      console.error("Error triggering AI review:", e);
      showToast("Couldn't start AI review at this time.", "error");
      _inflight.delete(persona);
      pendingPersonas = new Set([...pendingPersonas].filter(p => p !== persona));
      delete pendingSelections[persona];
    }
  }

  function formatDate(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return "just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  }

  function getAuthorName(comment) {
    if (comment.ai_persona) {
      return comment.ai_persona.charAt(0).toUpperCase() + comment.ai_persona.slice(1);
    }
    if (comment.author) {
      return comment.author.display_name || comment.author.email;
    }
    return "Unknown";
  }

  function canDelete(comment) {
    if (comment.ai_persona) return true;
    const userExternalId = getUserInfo().user?.externalId;
    return userExternalId && comment.author?.external_id === userExternalId;
  }

  function canResolve() {
    return currentPageRole === "admin" || currentPageRole === "editor";
  }

  async function handleApplySuggestion(comment) {
    if (!currentPageId || applyingComment) return;

    const view = window.editorView;
    if (!view) return;

    const field = view.state.field(commentHighlightField);
    const range = resolveAnchorRange(view.state, field.ranges, comment);

    if (!range) {
      showToast("Cannot locate the referenced text in the document");
      return;
    }

    applyingComment = comment.external_id;
    const personaName =
      comment.ai_persona.charAt(0).toUpperCase() + comment.ai_persona.slice(1);
    showToast(`Generating ${personaName}'s suggestion...`);

    try {
      // Call LLM to generate insertion text
      const { generateCommentEdit, createRewindCheckpoint } = getApi();
      const result = await generateCommentEdit(currentPageId, comment.external_id);
      const insertionText = result.text?.trim();

      if (!insertionText) {
        showToast(`${personaName} has nothing to add`);
        applyingComment = null;
        return;
      }

      // Create rewind checkpoint (pre-edit state)
      await createRewindCheckpoint(
        currentPageId,
        `Applied ${personaName}'s suggestion`,
      );

      // Re-resolve anchor range — the document may have changed during the
      // async LLM call and checkpoint request (local or remote edits shift offsets).
      const latestField = view.state.field(commentHighlightField);
      const latestRange = resolveAnchorRange(view.state, latestField.ranges, comment);
      if (!latestRange) {
        showToast("Anchor moved during generation — edit not applied");
        applyingComment = null;
        return;
      }

      // Insert after the paragraph containing the anchor
      const change = buildSuggestionChange(view.state, latestRange, insertionText);
      view.dispatch({ changes: change });

      // Temporarily highlight the inserted text
      const insertStart = change.from + 2; // skip the \n\n prefix
      const insertEnd = insertStart + insertionText.length;
      highlightInsertedText(view, insertStart, insertEnd);

      view.focus();

      // Auto-resolve the comment — call the API directly so we can detect failure
      // (handleResolve swallows errors and shows its own toast).
      let resolveSucceeded = false;
      try {
        const { resolveComment } = getApi();
        await resolveComment(currentPageId, comment.external_id);
        resolveSucceeded = true;
        await loadComments();
      } catch (e) {
        console.error("Error resolving after apply:", e);
      }

      showToast(
        resolveSucceeded
          ? `Applied ${personaName}'s suggestion. Discussion marked resolved`
          : `Applied ${personaName}'s suggestion`,
      );
    } catch (e) {
      console.error("Error applying AI suggestion:", e);
      showToast("Failed to apply suggestion");
    }

    applyingComment = null;
  }

  function highlightInsertedText(view, from, to) {
    // Select the inserted text so it's visually highlighted, then scroll to it.
    // This uses CodeMirror's native selection highlight which works correctly
    // with virtualized rendering (unlike direct DOM manipulation).
    const clampedTo = Math.min(to, view.state.doc.length);
    view.dispatch({
      selection: { anchor: from, head: clampedTo },
      effects: EditorView.scrollIntoView(from, { y: "center" }),
    });
  }

  function handleCommentClick(commentId) {
    activeCommentId = commentId;
    setActiveCommentHighlight(window.editorView, commentId);

    // Scroll editor to the comment's anchor position
    const view = window.editorView;
    if (!view) return;
    const field = view.state.field(commentHighlightField);
    const range = field.ranges.find((r) => r.commentId === commentId);
    if (range) {
      view.dispatch({
        effects: EditorView.scrollIntoView(range.from, { y: "center" }),
      });
    }
  }

  onMount(() => {
    registerTabHandler("comments", loadComments);
    registerPageChangeHandler((pageId) => {
      currentPageId = pageId;
      currentPageRole = window.getCurrentPage?.()?.role ?? null;
      _inflight.clear();
      pendingPersonas = new Set();
      loadComments();
    });

    commentsUpdatedHandler = () => {
      loadComments();
    };
    window.addEventListener("commentsUpdated", commentsUpdatedHandler);

    aiReviewCompleteHandler = (e) => {
      const { persona, commentCount } = e.detail;
      const wasPending = pendingPersonas.has(persona);
      _inflight.delete(persona);
      pendingPersonas = new Set([...pendingPersonas].filter(p => p !== persona));
      delete pendingSelections[persona];
      if (wasPending && commentCount === 0) {
        const name = PERSONAS[persona]?.name ?? persona;
        showToast(`${name} has nothing to add right now`);
      }
    };
    window.addEventListener("aiReviewComplete", aiReviewCompleteHandler);

    // Editor → Sidebar: clicking a comment bar/dot scrolls sidebar to that card
    commentFocusedHandler = (e) => {
      const { commentId } = e.detail;
      activeCommentId = commentId;
      openSidebar();
      setActiveTab("comments");
      requestAnimationFrame(() => {
        const card = document.querySelector(`.comment-card[data-comment-id="${commentId}"]`);
        if (card) {
          card.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      });
    };
    window.addEventListener("commentFocused", commentFocusedHandler);

    // Re-resolve comment anchors when document content changes so bars/dots track edits
    docChangeHandler = () => {
      if (!comments.length) return;
      if (docChangeTimer) clearTimeout(docChangeTimer);
      docChangeTimer = setTimeout(() => {
        resolveAndHighlight();
        docChangeTimer = null;
      }, 500);
    };
    window.addEventListener("editorContentChanged", docChangeHandler);

    // Re-resolve when collab connects (ydoc/ytext now available, though not yet synced).
    collabStatusHandler = (e) => {
      if (e.detail?.status === "connected" && comments.length) {
        resolveAndHighlight();
      }
    };
    window.addEventListener("collabStatus", collabStatusHandler);

    // Subscribe to rewind state
    isRewindMode = getRewindState().isRewindMode;
    unsubscribeRewind = subscribeRewind((state) => {
      isRewindMode = state.isRewindMode;
    });

    loadComments();
  });

  // Track editor selection for the AI review hint
  function checkEditorSelection() {
    const view = window.editorView;
    if (!view) { hasEditorSelection = false; return; }
    const sel = view.state.selection.main;
    hasEditorSelection = sel.from !== sel.to;
  }
  document.addEventListener("mouseup", checkEditorSelection);
  document.addEventListener("keyup", checkEditorSelection);

  onDestroy(() => {
    document.removeEventListener("mouseup", checkEditorSelection);
    document.removeEventListener("keyup", checkEditorSelection);
    if (commentsUpdatedHandler) {
      window.removeEventListener("commentsUpdated", commentsUpdatedHandler);
    }
    if (aiReviewCompleteHandler) {
      window.removeEventListener("aiReviewComplete", aiReviewCompleteHandler);
    }
    if (unsubscribeRewind) {
      unsubscribeRewind();
    }
    if (commentFocusedHandler) {
      window.removeEventListener("commentFocused", commentFocusedHandler);
    }
    if (docChangeHandler) {
      window.removeEventListener("editorContentChanged", docChangeHandler);
    }
    if (collabStatusHandler) {
      window.removeEventListener("collabStatus", collabStatusHandler);
    }
    if (docChangeTimer) {
      clearTimeout(docChangeTimer);
    }
    if (resolveRetryTimer) {
      clearTimeout(resolveRetryTimer);
    }
    // Clear highlights when tab is destroyed
    updateCommentHighlights(window.editorView, []);
  });
</script>

{#snippet renderReply(reply, threadResolved)}
  <div class="comment-reply">
    <div class="comment-header">
      {#if reply.ai_persona}
        <span class="comment-avatar comment-avatar-small comment-avatar-ai" style="background-image: url({PERSONA_SPRITE_URL}); background-position: {PERSONAS[reply.ai_persona]?.bgPosition || '0 0'}; background-size: 200% 200%;"></span>
      {:else}
        <span class="comment-avatar comment-avatar-small">{getAuthorName(reply).charAt(0).toUpperCase()}</span>
      {/if}
      <span class="comment-author">{getAuthorName(reply)}</span>
      <span class="comment-time">{formatDate(reply.created)}</span>
    </div>
    <div class="comment-body">{@html formatCommentBody(reply.body)}</div>
    <div class="comment-actions">
      <button class="comment-action-btn" disabled={threadResolved || reply.can_reply === false} title={threadResolved ? "Thread is resolved" : reply.can_reply === false ? "Maximum thread depth reached" : ""} onclick={() => startReply(reply.external_id)}>
        Reply
      </button>
      {#if canDelete(reply)}
        {#if confirmingDelete === reply.external_id}
          <button class="comment-action-btn comment-action-confirm" onclick={() => handleDelete(reply.external_id)}>Confirm</button>
          <button class="comment-action-btn" onclick={() => cancelDelete()}>Cancel</button>
        {:else}
          <button class="comment-action-btn comment-action-delete" onclick={() => handleDelete(reply.external_id)}>
            Delete
          </button>
        {/if}
      {/if}
    </div>
    {#if reply.replies && reply.replies.length > 0}
      <div class="comment-replies">
        {#each reply.replies as childReply (childReply.external_id)}
          {@render renderReply(childReply, threadResolved)}
        {/each}
      </div>
    {/if}
    {#if replyingTo === reply.external_id}
      <div class="comment-reply-input">
        <textarea
          class="comment-textarea"
          placeholder="Write a reply..."
          bind:value={replyBody}
          onkeydown={(e) => {
            if (e.key === "Escape") { replyingTo = null; replyBody = ""; }
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); handleReply(reply.external_id); }
          }}
        ></textarea>
        <div class="comment-input-actions">
          <button class="comment-cancel-btn" onclick={() => { replyingTo = null; replyBody = ""; }}>Cancel</button>
          <button class="comment-submit-btn" onclick={() => handleReply(reply.external_id)} disabled={!replyBody.trim()}>Reply</button>
        </div>
        <div class="comment-shortcut-hint">{navigator.platform?.includes("Mac") ? "⌘" : "Ctrl"} Enter</div>
      </div>
    {/if}
  </div>
{/snippet}

{#snippet replyTree(comment)}
  {#if comment.replies && comment.replies.length > 0}
    <div class="comment-replies">
      {#each comment.replies as reply (reply.external_id)}
        {@render renderReply(reply, comment.is_resolved)}
      {/each}
    </div>
  {/if}
  {#if replyingTo === comment.external_id}
    <div class="comment-reply-input">
      <textarea
        class="comment-textarea"
        placeholder="Write a reply..."
        bind:value={replyBody}
        onkeydown={(e) => {
          if (e.key === "Escape") { replyingTo = null; replyBody = ""; }
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); handleReply(comment.external_id); }
        }}
      ></textarea>
      <div class="comment-input-actions">
        <button class="comment-cancel-btn" onclick={() => { replyingTo = null; replyBody = ""; }}>Cancel</button>
        <button class="comment-submit-btn" onclick={() => handleReply(comment.external_id)} disabled={!replyBody.trim()}>Reply</button>
      </div>
      <div class="comment-shortcut-hint">{navigator.platform?.includes("Mac") ? "⌘" : "Ctrl"} Enter</div>
    </div>
  {/if}
{/snippet}

<div class="comments-content">
  {#if isRewindMode}
    <div class="comments-rewind-notice">
      <p>Discussions are hidden during Rewind mode.</p>
      <button class="comment-submit-btn" onclick={() => exitRewindMode()}>Exit Rewind</button>
    </div>
  {:else if loading}
    <div class="comments-loading">Loading...</div>
  {:else}
    <div class="comments-ai-triggers">
      {#each Object.entries(PERSONAS) as [key, persona]}
        <button class="ai-trigger-btn" class:ai-trigger-pending={pendingPersonas.has(key)} title="{persona.name}: {hasEditorSelection ? 'Review selection' : persona.subtitle}" disabled={pendingPersonas.has(key)} onclick={() => handleTriggerAIReview(key)}>
          <span class="ai-trigger-img" style="background-image: url({PERSONA_SPRITE_URL}); background-position: {persona.bgPosition}; background-size: 200% 200%;"></span>
          <span class="ai-trigger-label">{persona.name}</span>
        </button>
      {/each}
    </div>
    <div class="ai-review-status">
      {#if pendingPersonas.size > 0}
        {@const hasSelection = [...pendingPersonas].some(p => pendingSelections[p])}
        {[...pendingPersonas].map(p => PERSONAS[p]?.name).join(", ")}
        {pendingPersonas.size === 1 ? "is" : "are"} reviewing your {hasSelection ? "selection" : "page"}...
      {:else if hasEditorSelection}
        <span class="ai-selection-hint">Review selected text</span>
      {/if}
    </div>

    {#if getResolvedCount() > 0}
      <div class="comments-resolved-bar">
        <span class="comments-resolved-count">{getResolvedCount()} resolved</span>
        <button class="comments-resolved-toggle" onclick={() => toggleShowResolved()}>
          {showResolved ? "Hide" : "Show"}
        </button>
      </div>
    {/if}

    {#if comments.length === 0}
      <div class="comments-empty">
        <p class="comments-empty-text">No discussions yet</p>
        <p class="comments-empty-hint">Select text in the editor to start a discussion</p>
      </div>
    {:else if getVisibleComments().length === 0}
      <div class="comments-empty">
        <p class="comments-empty-text">All discussions resolved</p>
        <p class="comments-empty-hint">
          <button class="comments-resolved-toggle" onclick={() => toggleShowResolved()}>Show resolved</button>
        </p>
      </div>
    {:else}
      <div class="comments-list">
        {#each getVisibleComments() as comment (comment.external_id)}
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <div class="comment-card" class:comment-card-ai={comment.ai_persona} class:comment-card-active={activeCommentId === comment.external_id} class:comment-card-resolved={comment.is_resolved} data-comment-id={comment.external_id} onclick={() => handleCommentClick(comment.external_id)} animate:flip={{ duration: 200 }} transition:slide={{ duration: 200 }}>
            <div class="comment-header">
              {#if comment.ai_persona}
                <span class="comment-avatar comment-avatar-ai" style="background-image: url({PERSONA_SPRITE_URL}); background-position: {PERSONAS[comment.ai_persona]?.bgPosition || '0 0'}; background-size: 200% 200%;"></span>
              {:else}
                <span class="comment-avatar">{getAuthorName(comment).charAt(0).toUpperCase()}</span>
              {/if}
              <span class="comment-author">
                {getAuthorName(comment)}
                {#if comment.ai_persona}
                  <span class="comment-ai-badge">AI</span>
                {/if}
              </span>
              <span class="comment-time">{formatDate(comment.created)}</span>
              {#if !comment.parent_id && canResolve()}
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <!-- svelte-ignore a11y_no_static_element_interactions -->
                <span
                  class="comment-resolve-btn"
                  class:comment-resolve-btn-resolved={comment.is_resolved}
                  title={comment.is_resolved ? "Unresolve" : "Resolve"}
                  onclick={(e) => { e.stopPropagation(); comment.is_resolved ? handleUnresolve(comment.external_id) : handleResolve(comment.external_id); }}
                >
                  {#if comment.is_resolved}
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                  {:else}
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="9 12 12 15 16 10"/></svg>
                  {/if}
                </span>
              {/if}
            </div>

            {#if comment.anchor_text}
              <div class="comment-anchor-quote">{comment.anchor_text}</div>
            {/if}
            <div class="comment-body">{@html formatCommentBody(comment.body)}</div>

            <div class="comment-actions">
              {#if comment.ai_persona && !comment.parent_id && !comment.is_resolved && comment.anchor_text && canResolve()}
                <button
                  class="comment-action-btn"
                  disabled={applyingComment === comment.external_id}
                  onclick={(e) => { e.stopPropagation(); handleApplySuggestion(comment); }}
                >
                  {applyingComment === comment.external_id ? "Applying..." : "Apply"}
                </button>
              {/if}
              <button class="comment-action-btn" disabled={comment.is_resolved || comment.can_reply === false} title={comment.is_resolved ? "Thread is resolved" : comment.can_reply === false ? "Maximum thread depth reached" : ""} onclick={() => startReply(comment.external_id)}>
                Reply
              </button>
              {#if canDelete(comment)}
                {#if confirmingDelete === comment.external_id}
                  <button class="comment-action-btn comment-action-confirm" onclick={() => handleDelete(comment.external_id)}>Confirm</button>
                  <button class="comment-action-btn" onclick={() => cancelDelete()}>Cancel</button>
                {:else}
                  <button class="comment-action-btn comment-action-delete" onclick={() => handleDelete(comment.external_id)}>
                    Delete
                  </button>
                {/if}
              {/if}
            </div>

            <!-- Replies (recursive) -->
            {@render replyTree(comment)}
          </div>
        {/each}
      </div>
    {/if}

    <div class="comment-new-input">
      {#if showNewComment}
        <textarea
          class="comment-textarea"
          placeholder="Write a comment..."
          bind:value={pageCommentBody}
          onkeydown={(e) => {
            if (e.key === "Escape") { showNewComment = false; pageCommentBody = ""; }
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); handleCreatePageComment(); }
          }}
        ></textarea>
        <div class="comment-input-actions">
          <button class="comment-cancel-btn" onclick={() => { showNewComment = false; pageCommentBody = ""; }}>Cancel</button>
          <button class="comment-submit-btn" onclick={() => handleCreatePageComment()} disabled={!pageCommentBody.trim()}>Comment</button>
        </div>
        <div class="comment-shortcut-hint">{navigator.platform?.includes("Mac") ? "⌘" : "Ctrl"} Enter</div>
      {:else}
        <button class="comment-new-btn" onclick={async () => { showNewComment = true; await tick(); document.querySelector('.comment-new-input .comment-textarea')?.focus(); }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          Comment
        </button>
      {/if}
    </div>
  {/if}
</div>

<style>
  .comments-content {
    padding: 0.75rem;
    height: 100%;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .comments-loading {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    color: var(--text-secondary);
  }

  .comments-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 2rem 1rem;
    text-align: center;
  }

  .comments-empty-text {
    font-size: 0.875rem;
    color: var(--text-secondary, #666);
    margin: 0 0 0.25rem;
  }

  .comments-empty-hint {
    font-size: 0.75rem;
    color: var(--text-tertiary, #aaa);
    margin: 0;
  }

  .comments-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .comment-card {
    padding: 0.375rem 0.5rem;
    cursor: pointer;
    border-radius: 6px;
  }

  .comment-card + .comment-card {
    border-top: 1px solid var(--border-light, rgba(0, 0, 0, 0.06));
  }

  .comment-card-active {
    background: rgba(255, 180, 0, 0.06);
  }

  .comment-header {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    margin-bottom: 0.375rem;
  }

  .comment-avatar {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: var(--bg-elevated, #e5e5e5);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.625rem;
    font-weight: 600;
    color: var(--text-secondary, #666);
    flex-shrink: 0;
  }

  .comment-avatar-ai {
    background-repeat: no-repeat;
    background-color: transparent;
  }

  .comment-avatar-small {
    width: 16px;
    height: 16px;
    font-size: 0.5625rem;
  }

  .comment-author {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-primary, #333);
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }

  .comment-ai-badge {
    font-size: 0.5625rem;
    font-weight: 600;
    color: #7c3aed;
    background: rgba(124, 58, 237, 0.1);
    padding: 0.0625rem 0.25rem;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .comment-time {
    font-size: 0.6875rem;
    color: var(--text-tertiary, #aaa);
    margin-left: auto;
  }

  .comment-anchor-quote {
    font-size: 0.75rem;
    color: var(--text-secondary, #666);
    border-left: 2px solid var(--border-light, rgba(0, 0, 0, 0.12));
    padding-left: 0.5rem;
    margin-bottom: 0.25rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .comment-body {
    font-size: 0.8125rem;
    color: var(--text-primary, #333);
    line-height: 1.4;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .comment-new-btn {
    font-size: 0.8125rem;
    color: var(--text-secondary, #666);
    background: none;
    border: none;
    cursor: pointer;
    padding: 0.375rem 0;
    text-align: left;
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  .comment-new-btn:hover {
    color: var(--text-primary, #333);
  }

  .comment-shortcut-hint {
    font-size: 0.6875rem;
    color: var(--text-tertiary, #aaa);
    text-align: right;
  }

  .comment-actions {
    display: flex;
    gap: 0.25rem;
    align-items: center;
    margin-top: 0.375rem;
  }

  .comment-actions .comment-action-btn + .comment-action-btn::before {
    content: "\00b7";
    margin-right: 0.25rem;
    color: var(--text-tertiary, #aaa);
    pointer-events: none;
  }

  .comment-action-btn {
    font-size: 0.6875rem;
    color: var(--text-tertiary, #aaa);
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
  }

  .comment-action-btn:hover:not(:disabled) {
    color: var(--text-secondary, #666);
  }

  .comment-action-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .comment-action-delete:hover {
    color: #dc2626;
  }

  .comment-action-confirm {
    color: #dc2626;
  }

  .comment-replies {
    margin-top: 0.5rem;
    padding-left: 1rem;
    border-left: 1px solid var(--border-light, rgba(0, 0, 0, 0.08));
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .comment-reply {
    padding: 0.375rem 0;
  }

  .comment-reply-input {
    margin-top: 0.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .comment-textarea {
    width: 100%;
    min-height: 3rem;
    padding: 0.375rem 0.5rem;
    border: 1px solid var(--border-light, rgba(0, 0, 0, 0.12));
    border-radius: 6px;
    font-size: 0.8125rem;
    font-family: inherit;
    resize: vertical;
    background: var(--bg-primary, #fff);
    color: var(--text-primary, #333);
    box-sizing: border-box;
  }

  .comment-textarea:focus {
    outline: none;
    border-color: var(--accent, #0969da);
  }

  .comment-input-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.375rem;
  }

  .comment-cancel-btn {
    font-size: 0.75rem;
    color: var(--text-secondary, #666);
    background: none;
    border: none;
    cursor: pointer;
    padding: 0.25rem 0.5rem;
  }

  .comment-submit-btn {
    font-size: 0.75rem;
    color: #fff;
    background: var(--accent, #0969da);
    border: none;
    border-radius: 4px;
    cursor: pointer;
    padding: 0.25rem 0.75rem;
  }

  .comment-submit-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .ai-selection-hint {
    color: var(--accent, #0969da);
  }

  .comments-ai-triggers {
    display: flex;
    gap: 0.375rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border-light, rgba(0, 0, 0, 0.06));
  }

  .ai-trigger-btn {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.25rem;
    padding: 0.375rem;
    background: var(--bg-surface, #fafafa);
    border: 1px solid var(--border-light, rgba(0, 0, 0, 0.1));
    border-radius: 6px;
    cursor: pointer;
    position: relative;
    flex: 1;
    min-width: 0;
  }

  .ai-trigger-btn:hover:not(:disabled) {
    background: var(--bg-elevated, #e5e5e5);
    border-color: var(--border-medium, rgba(0, 0, 0, 0.2));
  }

  .ai-trigger-btn:disabled {
    cursor: not-allowed;
  }

  .ai-trigger-img {
    width: 100%;
    aspect-ratio: 1;
    border-radius: 4px;
    background-repeat: no-repeat;
    filter: grayscale(1);
    transition: filter 0.3s ease;
  }

  .ai-trigger-btn:hover:not(:disabled) .ai-trigger-img {
    filter: grayscale(0);
  }

  .ai-trigger-pending .ai-trigger-img {
    filter: grayscale(0);
  }

  .ai-trigger-pending {
    animation: persona-pulse 2s ease-in-out infinite;
  }

  @keyframes persona-pulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(124, 58, 237, 0); }
    50% { box-shadow: 0 0 8px 2px rgba(124, 58, 237, 0.3); }
  }

  .ai-trigger-label {
    font-size: 0.6875rem;
    font-weight: 500;
    color: var(--text-secondary, #666);
  }

  .ai-review-status {
    font-size: 0.75rem;
    color: var(--text-secondary, #666);
    min-height: 1.25rem;
    text-align: center;
  }

  .comment-new-input {
    margin-top: auto;
    padding-top: 0.5rem;
    border-top: 1px solid var(--border-light, rgba(0, 0, 0, 0.06));
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .comment-link {
    color: var(--accent, #0969da);
    text-decoration: underline;
  }

  .comment-link:hover {
    text-decoration: none;
  }

  .comments-rewind-notice {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    padding: 2rem 1rem;
    text-align: center;
    color: var(--text-secondary, #666);
    font-size: 0.8125rem;
  }

  .comments-rewind-notice p {
    margin: 0;
  }

  /* Resolved filter bar */
  .comments-resolved-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.375rem 0.5rem;
    font-size: 0.75rem;
    color: var(--text-secondary, #666);
    border-bottom: 1px solid var(--border-light, rgba(0, 0, 0, 0.06));
  }

  .comments-resolved-count {
    color: var(--text-tertiary, #aaa);
  }

  .comments-resolved-toggle {
    font-size: 0.75rem;
    color: var(--accent, #0969da);
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
  }

  .comments-resolved-toggle:hover {
    text-decoration: underline;
  }

  /* Resolve button (checkmark in header) */
  .comment-resolve-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    cursor: pointer;
    color: var(--text-tertiary, #aaa);
    border-radius: 50%;
    flex-shrink: 0;
  }

  .comment-resolve-btn:hover {
    color: #16a34a;
    background: rgba(22, 163, 74, 0.08);
  }

  .comment-resolve-btn-resolved {
    color: #16a34a;
  }

  .comment-resolve-btn-resolved:hover {
    color: var(--text-tertiary, #aaa);
    background: rgba(0, 0, 0, 0.04);
  }

  /* Resolved card styling */
  .comment-card-resolved {
    opacity: 0.55;
  }

  .comment-card-resolved:hover {
    opacity: 0.85;
  }

  /* Dark mode */
  :global(.dark) .comment-card-active {
    background: rgba(255, 180, 0, 0.08);
  }

  :global(.dark) .comment-textarea {
    background: var(--bg-surface, #1e1e1e);
    border-color: var(--border-light, rgba(255, 255, 255, 0.12));
    color: var(--text-primary, #e0e0e0);
  }

  :global(.dark) .ai-trigger-btn {
    background: var(--bg-surface, #1e1e1e);
    border-color: var(--border-light, rgba(255, 255, 255, 0.1));
  }

  :global(.dark) .ai-trigger-btn:hover:not(:disabled) {
    background: var(--bg-elevated, #2a2a2a);
  }

  :global(.dark) .comment-resolve-btn-resolved:hover {
    background: rgba(255, 255, 255, 0.06);
  }

</style>
