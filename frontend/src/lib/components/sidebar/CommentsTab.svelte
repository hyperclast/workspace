<script>
  import { onMount, onDestroy, tick } from "svelte";
  import { flip } from "svelte/animate";
  import { slide } from "svelte/transition";
  import { PERSONAS, PERSONA_SPRITE_URL } from "../../personaImages.js";
  import { registerTabHandler, registerPageChangeHandler, getState, openSidebar, setActiveTab } from "../../stores/sidebar.svelte.js";
  import {
    fetchComments as apiFetchComments,
    fetchReplies as apiFetchReplies,
    createComment as apiCreateComment,
    deleteComment as apiDeleteComment,
    triggerAIReview as apiTriggerAIReview,
  } from "../../../api.js";
  import { isDemoMode } from "../../../demo/index.js";
  import {
    fetchComments as demoFetchComments,
    fetchReplies as demoFetchReplies,
    createComment as demoCreateComment,
    deleteComment as demoDeleteComment,
    triggerAIReview as demoTriggerAIReview,
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
      ? { fetchComments: demoFetchComments, fetchReplies: demoFetchReplies, createComment: demoCreateComment, deleteComment: demoDeleteComment, triggerAIReview: demoTriggerAIReview }
      : { fetchComments: apiFetchComments, fetchReplies: apiFetchReplies, createComment: apiCreateComment, deleteComment: apiDeleteComment, triggerAIReview: apiTriggerAIReview };
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function formatCommentBody(content) {
    const escaped = escapeHtml(content);
    return escaped
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\[(.*?)\]\((https?:\/\/[^\s)]+)\)/g, '<a class="comment-link" href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
      .replace(/\n/g, "<br>");
  }

  let comments = $state([]);
  let currentPageId = $state(null);
  let loading = $state(false);
  let loadingMoreReplies = $state(null);
  let replyingTo = $state(null); // external_id of comment being replied to
  let expandedReplyIds = new Set(); // comment IDs whose deeper replies have been loaded
  let pageCommentBody = $state("");
  let replyBody = $state("");

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

    const ranges = resolveCommentAnchors(comments, currentPageId, view, ydoc, ytext);
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

  /**
   * Find a comment by external_id anywhere in the tree.
   */
  function findInTree(items, targetId) {
    for (const c of items) {
      if (c.external_id === targetId) return c;
      if (c.replies?.length > 0) {
        const found = findInTree(c.replies, targetId);
        if (found) return found;
      }
    }
    return null;
  }

  /**
   * Re-expand any replies that were previously loaded at deeper nesting levels.
   * Called after loadComments to restore nested reply state.
   */
  async function reExpandDeepReplies() {
    if (expandedReplyIds.size === 0) return;
    const { fetchReplies } = getApi();
    for (const id of expandedReplyIds) {
      const comment = findInTree(comments, id);
      if (!comment || (comment.replies_count || 0) === 0) continue;
      const loaded = comment.replies?.length || 0;
      if (loaded >= comment.replies_count) continue;
      try {
        const data = await fetchReplies(currentPageId, id, 20, loaded);
        comments = updateInTree(comments, id, (c) => ({
          ...c,
          replies: [...(c.replies || []), ...data.items],
        }));
      } catch (e) {
        // Stale ID — comment was deleted; remove from tracking set
        expandedReplyIds.delete(id);
      }
    }
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
      await reExpandDeepReplies();
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

  /**
   * Recursively find a comment by external_id and apply an updater function.
   * Works at any nesting depth.
   */
  function updateInTree(items, targetId, updater) {
    return items.map((c) => {
      if (c.external_id === targetId) return updater(c);
      if (c.replies?.length > 0) {
        return { ...c, replies: updateInTree(c.replies, targetId, updater) };
      }
      return c;
    });
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

      // Track that this parent has expanded nested replies so loadComments
      // re-fetches them after the server-pushed refresh.
      const parent = findInTree(comments, parentId);
      if (parent?.parent_id) {
        // Replying to a non-root comment — track the parent for re-expansion
        expandedReplyIds.add(parentId);
      }

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

  const _inflight = new Set(); // synchronous guard — $state batching can't be trusted for dedup
  async function handleTriggerAIReview(persona) {
    if (!currentPageId || _inflight.has(persona)) return;
    _inflight.add(persona);
    pendingPersonas = new Set([...pendingPersonas, persona]);
    try {
      const { triggerAIReview } = getApi();
      await triggerAIReview(currentPageId, persona);
      // Comments will arrive via WebSocket commentsUpdated event
    } catch (e) {
      console.error("Error triggering AI review:", e);
      showToast("Couldn't start AI review at this time.", "error");
      _inflight.delete(persona);
      pendingPersonas = new Set([...pendingPersonas].filter(p => p !== persona));
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

  async function handleLoadMoreReplies(comment) {
    if (!currentPageId || loadingMoreReplies) return;
    const loadedCount = comment.replies?.length || 0;
    if (loadedCount >= (comment.replies_count || 0)) return;

    loadingMoreReplies = comment.external_id;
    try {
      const { fetchReplies } = getApi();
      const data = await fetchReplies(currentPageId, comment.external_id, 20, loadedCount);
      comments = updateInTree(comments, comment.external_id, (c) => ({
        ...c,
        replies: [...(c.replies || []), ...data.items],
      }));
      // Track so loadComments preserves this expansion
      expandedReplyIds.add(comment.external_id);
      resolveAndHighlight();
    } finally {
      loadingMoreReplies = null;
    }
  }

  onMount(() => {
    registerTabHandler("comments", loadComments);
    registerPageChangeHandler((pageId) => {
      currentPageId = pageId;
      loadComments();
    });

    commentsUpdatedHandler = () => {
      loadComments();
      // Fallback: clear pending in case ai_review_complete event was lost
      _inflight.clear();
      pendingPersonas = new Set();
    };
    window.addEventListener("commentsUpdated", commentsUpdatedHandler);

    aiReviewCompleteHandler = (e) => {
      const { persona, commentCount } = e.detail;
      const wasPending = pendingPersonas.has(persona);
      _inflight.delete(persona);
      pendingPersonas = new Set([...pendingPersonas].filter(p => p !== persona));
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

  onDestroy(() => {
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

{#snippet renderReply(reply)}
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
      <button class="comment-action-btn" onclick={() => startReply(reply.external_id)}>
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
          {@render renderReply(childReply)}
        {/each}
      </div>
    {/if}
    {#if (reply.replies_count || 0) > (reply.replies?.length || 0)}
      <button
        class="comment-load-more"
        disabled={loadingMoreReplies === reply.external_id}
        onclick={() => handleLoadMoreReplies(reply)}
      >
        {loadingMoreReplies === reply.external_id
          ? "Loading..."
          : `Load more replies (${(reply.replies_count || 0) - (reply.replies?.length || 0)} more)`}
      </button>
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
        {@render renderReply(reply)}
      {/each}
    </div>
  {/if}
  {#if (comment.replies_count || 0) > (comment.replies?.length || 0)}
    <button
      class="comment-load-more"
      disabled={loadingMoreReplies === comment.external_id}
      onclick={() => handleLoadMoreReplies(comment)}
    >
      {loadingMoreReplies === comment.external_id
        ? "Loading..."
        : `Load more replies (${(comment.replies_count || 0) - (comment.replies?.length || 0)} more)`}
    </button>
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
      <p>Comments are hidden during Rewind mode.</p>
      <button class="comment-submit-btn" onclick={() => exitRewindMode()}>Exit Rewind</button>
    </div>
  {:else if loading}
    <div class="comments-loading">Loading...</div>
  {:else}
    <div class="comments-ai-triggers">
      {#each Object.entries(PERSONAS) as [key, persona]}
        <button class="ai-trigger-btn" class:ai-trigger-pending={pendingPersonas.has(key)} title="{persona.name} — {persona.subtitle}" disabled={pendingPersonas.has(key)} onclick={() => handleTriggerAIReview(key)}>
          <span class="ai-trigger-img" style="background-image: url({PERSONA_SPRITE_URL}); background-position: {persona.bgPosition}; background-size: 200% 200%;"></span>
          <span class="ai-trigger-label">{persona.name}</span>
        </button>
      {/each}
    </div>
    <div class="ai-review-status">
      {#if pendingPersonas.size > 0}
        {[...pendingPersonas].map(p => PERSONAS[p]?.name).join(", ")}
        {pendingPersonas.size === 1 ? "is" : "are"} reviewing your page...
      {/if}
    </div>

    {#if comments.length === 0}
      <div class="comments-empty">
        <p class="comments-empty-text">No comments yet</p>
        <p class="comments-empty-hint">Select text in the editor and add a comment</p>
      </div>
    {:else}
      <div class="comments-list">
        {#each comments as comment (comment.external_id)}
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <div class="comment-card" class:comment-card-ai={comment.ai_persona} class:comment-card-active={activeCommentId === comment.external_id} data-comment-id={comment.external_id} onclick={() => handleCommentClick(comment.external_id)} animate:flip={{ duration: 200 }} transition:slide={{ duration: 200 }}>
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
            </div>

            {#if comment.anchor_text}
              <div class="comment-anchor-quote">{comment.anchor_text}</div>
            {/if}
            <div class="comment-body">{@html formatCommentBody(comment.body)}</div>

            <div class="comment-actions">
              <button class="comment-action-btn" onclick={() => startReply(comment.external_id)}>
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
    gap: 0.5rem;
    margin-top: 0.375rem;
  }

  .comment-action-btn {
    font-size: 0.6875rem;
    color: var(--text-tertiary, #aaa);
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
  }

  .comment-action-btn:hover {
    color: var(--text-secondary, #666);
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

  .comment-load-more {
    margin-top: 0.375rem;
    font-size: 0.6875rem;
    color: var(--text-tertiary, #aaa);
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
    text-align: left;
  }

  .comment-load-more:hover:not(:disabled) {
    color: var(--accent, #0969da);
  }

  .comment-load-more:disabled {
    cursor: not-allowed;
    opacity: 0.7;
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

</style>
