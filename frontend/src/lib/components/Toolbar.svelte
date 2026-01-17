<script>
  import { onMount } from "svelte";
  import { foldAll, unfoldAll } from "@codemirror/language";
  import {
    ChevronsDownUp,
    ChevronsUpDown,
    Table2,
    Bold,
    Underline,
    Italic,
    Strikethrough,
    List,
    ListOrdered,
    Search,
    CheckSquare,
    Quote,
    Code,
    FileCode,
    Link2,
    Undo2,
    Redo2,
    CircleHelp,
    MoreHorizontal
  } from "lucide-static";
  import { openSidebar, setActiveTab } from "../stores/sidebar.svelte.js";
  import { toggleCheckbox } from "../../decorateFormatting.js";
  import { helpModal } from "../modal.js";
  import LinkModal from "./LinkModal.svelte";

  let { editorView = $bindable(null), tableUtils = null } = $props();

  let headingMenuOpen = $state(false);
  let linkModalOpen = $state(false);
  let linkModalInitialTitle = $state('');
  let linkModalInitialUrl = $state('');
  let linkInsertPosition = $state({ from: 0, to: 0 });
  let linkEditMode = $state(false);

  // Overflow menu state
  let overflowOpen = $state(false);
  let containerRef = $state(null);
  let containerWidth = $state(0);
  let itemWidths = $state([]);
  let measurementComplete = $state(false);

  function toggleFormat(marker) {
    if (!editorView) return;
    const { state } = editorView;
    const { from, to } = state.selection.main;
    const markerLen = marker.length;

    if (from === to) {
      const wrapped = marker + marker;
      editorView.dispatch({
        changes: { from, insert: wrapped },
        selection: { anchor: from + markerLen },
      });
      editorView.focus();
      return;
    }

    const selectedText = state.sliceDoc(from, to);

    const beforeStart = Math.max(0, from - markerLen);
    const afterEnd = Math.min(state.doc.length, to + markerLen);
    const textBefore = state.sliceDoc(beforeStart, from);
    const textAfter = state.sliceDoc(to, afterEnd);

    if (textBefore === marker && textAfter === marker) {
      editorView.dispatch({
        changes: [
          { from: beforeStart, to: from, insert: "" },
          { from: to, to: afterEnd, insert: "" },
        ],
        selection: { anchor: beforeStart, head: beforeStart + selectedText.length },
      });
    } else if (selectedText.startsWith(marker) && selectedText.endsWith(marker) && selectedText.length >= markerLen * 2) {
      const inner = selectedText.slice(markerLen, -markerLen);
      editorView.dispatch({
        changes: { from, to, insert: inner },
        selection: { anchor: from, head: from + inner.length },
      });
    } else {
      const wrapped = marker + selectedText + marker;
      editorView.dispatch({
        changes: { from, to, insert: wrapped },
        selection: { anchor: from, head: from + wrapped.length },
      });
    }
    editorView.focus();
  }

  function toggleLinePrefix(prefix) {
    if (!editorView) return;
    const { state } = editorView;
    const { from, to } = state.selection.main;

    const startLine = state.doc.lineAt(from);
    const endLine = state.doc.lineAt(to);

    const changes = [];
    let allHavePrefix = true;

    for (let lineNum = startLine.number; lineNum <= endLine.number; lineNum++) {
      const line = state.doc.line(lineNum);
      if (!line.text.startsWith(prefix)) {
        allHavePrefix = false;
        break;
      }
    }

    const headingPrefixes = ["# ", "## ", "### ", "#### ", "##### ", "###### "];
    const isHeadingPrefix = headingPrefixes.includes(prefix);

    let offset = 0;
    for (let lineNum = startLine.number; lineNum <= endLine.number; lineNum++) {
      const line = state.doc.line(lineNum);

      if (allHavePrefix) {
        changes.push({
          from: line.from + offset,
          to: line.from + offset + prefix.length,
          insert: ""
        });
        offset -= prefix.length;
      } else {
        let insertAt = line.from + offset;
        let removeEnd = insertAt;

        if (isHeadingPrefix) {
          const existingHeading = headingPrefixes.find(p => line.text.startsWith(p));
          if (existingHeading) {
            removeEnd = insertAt + existingHeading.length;
          }
        }

        changes.push({
          from: insertAt,
          to: removeEnd,
          insert: prefix
        });
        offset += prefix.length - (removeEnd - insertAt);
      }
    }

    const newCursorPos = startLine.from + (allHavePrefix ? 0 : prefix.length);
    editorView.dispatch({
      changes,
      selection: { anchor: newCursorPos }
    });
    editorView.focus();
    headingMenuOpen = false;
  }

  function toggleOrderedList() {
    if (!editorView) return;
    const { state } = editorView;
    const { from, to } = state.selection.main;

    const startLine = state.doc.lineAt(from);
    const endLine = state.doc.lineAt(to);

    const changes = [];
    const olPattern = /^\d+\.\s/;
    let allHavePrefix = true;

    for (let lineNum = startLine.number; lineNum <= endLine.number; lineNum++) {
      const line = state.doc.line(lineNum);
      if (!olPattern.test(line.text)) {
        allHavePrefix = false;
        break;
      }
    }

    let offset = 0;
    let itemNum = 1;
    let firstLinePrefix = "";

    for (let lineNum = startLine.number; lineNum <= endLine.number; lineNum++) {
      const line = state.doc.line(lineNum);
      const match = line.text.match(olPattern);

      if (allHavePrefix && match) {
        changes.push({
          from: line.from + offset,
          to: line.from + offset + match[0].length,
          insert: ""
        });
        offset -= match[0].length;
      } else {
        const prefix = `${itemNum}. `;
        if (lineNum === startLine.number) {
          firstLinePrefix = prefix;
        }
        let insertAt = line.from + offset;
        let removeLen = 0;

        if (match) {
          removeLen = match[0].length;
        }

        changes.push({
          from: insertAt,
          to: insertAt + removeLen,
          insert: prefix
        });
        offset += prefix.length - removeLen;
        itemNum++;
      }
    }

    const newCursorPos = startLine.from + (allHavePrefix ? 0 : firstLinePrefix.length);
    editorView.dispatch({
      changes,
      selection: { anchor: newCursorPos }
    });
    editorView.focus();
  }

  function handleFoldAll() {
    if (!editorView) return;
    foldAll(editorView);
    editorView.focus();
  }

  function handleUnfoldAll() {
    if (!editorView) return;
    unfoldAll(editorView);
    editorView.focus();
  }

  function handleUndo() {
    const um = window.undoManager;
    if (!um) return;
    um.undo();
    window.editorView?.focus();
  }

  function handleRedo() {
    const um = window.undoManager;
    if (!um) return;
    um.redo();
    window.editorView?.focus();
  }

  function insertTable() {
    if (!editorView || !tableUtils?.generateTable) return;

    const tableMarkdown = tableUtils.generateTable(2, 2);
    const cursor = editorView.state.selection.main.head;
    const headerStart = cursor + 2 + 2;
    const headerEnd = headerStart + "Header 1".length;

    editorView.dispatch({
      changes: { from: cursor, insert: '\n\n' + tableMarkdown + '\n\n' },
      selection: { anchor: headerStart, head: headerEnd }
    });
    editorView.focus();
  }

  function openAskTab() {
    openSidebar();
    setActiveTab("ask");

    setTimeout(() => {
      const input = document.getElementById("chat-input");
      if (input) {
        input.focus();
        input.classList.add("flash-highlight");
        setTimeout(() => input.classList.remove("flash-highlight"), 600);
      }
    }, 100);
  }

  function insertCodeBlock() {
    if (!editorView) return;
    const { state } = editorView;
    const { from, to } = state.selection.main;
    const selectedText = state.sliceDoc(from, to);

    if (selectedText.startsWith("```") && selectedText.endsWith("```")) {
      const inner = selectedText.slice(3, -3).replace(/^\n/, "").replace(/\n$/, "");
      editorView.dispatch({
        changes: { from, to, insert: inner },
        selection: { anchor: from, head: from + inner.length },
      });
    } else {
      const wrapped = "```\n" + (selectedText || "") + "\n```";
      const cursorPos = from + 4;
      editorView.dispatch({
        changes: { from, to, insert: wrapped },
        selection: { anchor: cursorPos, head: cursorPos + selectedText.length },
      });
    }
    editorView.focus();
  }

  function findLinkAtCursor(state, pos) {
    const line = state.doc.lineAt(pos);
    const lineText = line.text;
    const linkRegex = /\[([^\]]*)\]\(([^)]*)\)/g;
    let match;
    while ((match = linkRegex.exec(lineText)) !== null) {
      const linkStart = line.from + match.index;
      const linkEnd = linkStart + match[0].length;
      if (pos >= linkStart && pos <= linkEnd) {
        return {
          from: linkStart,
          to: linkEnd,
          title: match[1],
          url: match[2],
        };
      }
    }
    return null;
  }

  function insertLink() {
    if (!editorView) return;
    const { state } = editorView;
    const { from, to } = state.selection.main;
    const selectedText = state.sliceDoc(from, to);

    const existingLink = findLinkAtCursor(state, from);
    if (existingLink) {
      linkModalInitialTitle = existingLink.title;
      linkModalInitialUrl = existingLink.url;
      linkInsertPosition = { from: existingLink.from, to: existingLink.to };
      linkEditMode = true;
      linkModalOpen = true;
      return;
    }

    if (selectedText && /^\[.*\]\(.*\)$/.test(selectedText)) {
      const match = selectedText.match(/^\[([^\]]*)\]\(([^)]*)\)$/);
      if (match) {
        linkModalInitialTitle = match[1];
        linkModalInitialUrl = match[2];
        linkInsertPosition = { from, to };
        linkEditMode = true;
        linkModalOpen = true;
        return;
      }
    }

    linkModalInitialTitle = selectedText || '';
    linkModalInitialUrl = '';
    linkInsertPosition = { from, to };
    linkEditMode = false;
    linkModalOpen = true;
  }

  function handleLinkInsert({ url, title }) {
    if (!editorView) return;
    const { from, to } = linkInsertPosition;
    const linkMarkdown = linkEditMode ? `[${title}](${url})` : `[${title}](${url}) `;
    editorView.dispatch({
      changes: { from, to, insert: linkMarkdown },
      selection: { anchor: from + linkMarkdown.length },
    });
    editorView.focus();
    setTimeout(() => {
      window.dispatchEvent(new CustomEvent("editorEnterPressed"));
    }, 50);
  }

  // Define toolbar items as data for dynamic rendering
  const toolbarItems = [
    { type: 'button', id: 'undo', title: 'Undo (Cmd+Z)', icon: Undo2, action: handleUndo, label: 'Undo' },
    { type: 'button', id: 'redo', title: 'Redo (Cmd+Shift+Z)', icon: Redo2, action: handleRedo, label: 'Redo' },
    { type: 'separator' },
    { type: 'button', id: 'bold', title: 'Bold (Cmd+B)', icon: Bold, action: () => toggleFormat("**"), label: 'Bold' },
    { type: 'button', id: 'italic', title: 'Italic (Cmd+I)', icon: Italic, action: () => toggleFormat("*"), label: 'Italic' },
    { type: 'button', id: 'underline', title: 'Underline (Cmd+U)', icon: Underline, action: () => toggleFormat("__"), label: 'Underline' },
    { type: 'button', id: 'strikethrough', title: 'Strikethrough', icon: Strikethrough, action: () => toggleFormat("~~"), label: 'Strikethrough' },
    { type: 'button', id: 'code', title: 'Inline code', icon: Code, action: () => toggleFormat("`"), label: 'Inline code' },
    { type: 'button', id: 'codeblock', title: 'Code block', icon: FileCode, action: insertCodeBlock, label: 'Code block' },
    { type: 'button', id: 'link', title: 'Insert link (Cmd+K)', icon: Link2, action: insertLink, label: 'Insert link' },
    { type: 'separator' },
    { type: 'button', id: 'h2', title: 'Heading 2', text: 'H2', action: () => toggleLinePrefix("## "), label: 'Heading 2' },
    { type: 'button', id: 'h3', title: 'Heading 3', text: 'H3', action: () => toggleLinePrefix("### "), label: 'Heading 3' },
    { type: 'heading-dropdown', id: 'heading-menu' },
    { type: 'separator' },
    { type: 'button', id: 'bullet', title: 'Bullet list', icon: List, action: () => toggleLinePrefix("- "), label: 'Bullet list' },
    { type: 'button', id: 'numbered', title: 'Numbered list', icon: ListOrdered, action: toggleOrderedList, label: 'Numbered list' },
    { type: 'button', id: 'checklist', title: 'Checklist (Cmd+L)', icon: CheckSquare, action: () => { if (editorView) toggleCheckbox(editorView); }, label: 'Checklist' },
    { type: 'button', id: 'quote', title: 'Blockquote', icon: Quote, action: () => toggleLinePrefix("> "), label: 'Blockquote' },
    { type: 'separator' },
    { type: 'button', id: 'fold', title: 'Fold all sections', icon: ChevronsDownUp, action: handleFoldAll, label: 'Fold all' },
    { type: 'button', id: 'unfold', title: 'Expand all sections', icon: ChevronsUpDown, action: handleUnfoldAll, label: 'Expand all' },
    { type: 'button', id: 'ask', title: 'Ask AI', icon: Search, action: openAskTab, label: 'Ask AI' },
    { type: 'button', id: 'table', title: 'Insert table', icon: Table2, action: insertTable, label: 'Insert table' },
    { type: 'button', id: 'help', title: 'Keyboard shortcuts (?)', icon: CircleHelp, action: helpModal, label: 'Shortcuts' },
  ];

  const OVERFLOW_BTN_WIDTH = 36;
  const BUTTON_WIDTH = 32; // button (28px) + gap (4px)
  const TEXT_BUTTON_WIDTH = 36; // text buttons are slightly wider
  const SEPARATOR_WIDTH = 12; // separator (1px) + margins (8px)
  const HEADING_DROPDOWN_WIDTH = 40;

  // Calculate item width based on type
  function getItemWidth(item) {
    if (item.type === 'separator') return SEPARATOR_WIDTH;
    if (item.type === 'heading-dropdown') return HEADING_DROPDOWN_WIDTH;
    if (item.text) return TEXT_BUTTON_WIDTH;
    return BUTTON_WIDTH;
  }

  // Pre-calculate total widths
  const precomputedWidths = toolbarItems.map(getItemWidth);

  // Calculate visible count based on container width
  let visibleCount = $derived.by(() => {
    if (!containerWidth || !measurementComplete) return toolbarItems.length;

    let availableWidth = containerWidth - OVERFLOW_BTN_WIDTH - 8; // extra padding
    let count = 0;
    let totalWidth = 0;

    for (let i = 0; i < precomputedWidths.length; i++) {
      const width = precomputedWidths[i];
      if (totalWidth + width > availableWidth) break;
      totalWidth += width;
      count++;
    }

    // Don't cut off right after a separator - go back one
    if (count > 0 && count < toolbarItems.length && toolbarItems[count - 1].type === 'separator') {
      count--;
    }

    return count;
  });

  let visibleItems = $derived(toolbarItems.slice(0, visibleCount));
  let overflowItems = $derived(toolbarItems.slice(visibleCount));
  let hasOverflow = $derived(overflowItems.length > 0);

  // Filter overflow items to remove leading/trailing/consecutive separators
  let filteredOverflowItems = $derived.by(() => {
    const items = overflowItems.filter((item, i, arr) => {
      if (item.type !== 'separator') return true;
      // Remove leading separators
      if (i === 0) return false;
      // Remove trailing separators
      if (i === arr.length - 1) return false;
      // Remove consecutive separators
      if (arr[i - 1]?.type === 'separator') return false;
      return true;
    });
    return items;
  });

  onMount(() => {
    measurementComplete = true;

    const observer = new ResizeObserver(entries => {
      containerWidth = entries[0].contentRect.width;
    });

    if (containerRef) {
      observer.observe(containerRef);
    }

    return () => observer.disconnect();
  });

  function handleClickOutside(event) {
    if (headingMenuOpen && !event.target.closest('.toolbar-dropdown')) {
      headingMenuOpen = false;
    }
    if (overflowOpen && !event.target.closest('.toolbar-overflow')) {
      overflowOpen = false;
    }
  }
</script>

<svelte:document onclick={handleClickOutside} />

<div class="toolbar-wrapper">
  <div class="toolbar">
    <div class="toolbar-container" bind:this={containerRef}>
      {#each visibleItems as item}
        {#if item.type === 'separator'}
          <span class="toolbar-separator"></span>
        {:else if item.type === 'heading-dropdown'}
          <div class="toolbar-dropdown">
            <button
              class="toolbar-btn toolbar-btn-text"
              title="More headings"
              onmousedown={(e) => { e.preventDefault(); e.stopPropagation(); headingMenuOpen = !headingMenuOpen; }}
            >
              H<span class="dropdown-arrow">▾</span>
            </button>
            {#if headingMenuOpen}
              <div class="toolbar-dropdown-menu">
                <button onmousedown={(e) => { e.preventDefault(); toggleLinePrefix("# "); }}>Heading 1</button>
                <button onmousedown={(e) => { e.preventDefault(); toggleLinePrefix("#### "); }}>Heading 4</button>
                <button onmousedown={(e) => { e.preventDefault(); toggleLinePrefix("##### "); }}>Heading 5</button>
                <button onmousedown={(e) => { e.preventDefault(); toggleLinePrefix("###### "); }}>Heading 6</button>
              </div>
            {/if}
          </div>
        {:else if item.text}
          <button class="toolbar-btn toolbar-btn-text" title={item.title} onmousedown={(e) => { e.preventDefault(); item.action(); }}>
            {item.text}
          </button>
        {:else}
          <button class="toolbar-btn" title={item.title} onmousedown={(e) => { e.preventDefault(); item.action(); }}>
            {@html item.icon}
          </button>
        {/if}
      {/each}

      {#if hasOverflow}
        <div class="toolbar-dropdown toolbar-overflow">
          <button
            class="toolbar-btn"
            title="More options"
            onmousedown={(e) => { e.preventDefault(); e.stopPropagation(); overflowOpen = !overflowOpen; }}
          >
            {@html MoreHorizontal}
          </button>
          {#if overflowOpen}
            <div class="toolbar-dropdown-menu toolbar-overflow-menu">
              {#each filteredOverflowItems as item}
                {#if item.type === 'separator'}
                  <div class="overflow-separator"></div>
                {:else if item.type === 'heading-dropdown'}
                  <div class="overflow-submenu">
                    <span class="overflow-label">Headings</span>
                    <button onmousedown={(e) => { e.preventDefault(); toggleLinePrefix("# "); overflowOpen = false; }}>H1</button>
                    <button onmousedown={(e) => { e.preventDefault(); toggleLinePrefix("#### "); overflowOpen = false; }}>H4</button>
                    <button onmousedown={(e) => { e.preventDefault(); toggleLinePrefix("##### "); overflowOpen = false; }}>H5</button>
                    <button onmousedown={(e) => { e.preventDefault(); toggleLinePrefix("###### "); overflowOpen = false; }}>H6</button>
                  </div>
                {:else}
                  <button onmousedown={(e) => { e.preventDefault(); item.action(); overflowOpen = false; }}>
                    {#if item.icon}
                      <span class="overflow-icon">{@html item.icon}</span>
                    {/if}
                    <span>{item.label}</span>
                  </button>
                {/if}
              {/each}
            </div>
          {/if}
        </div>
      {/if}
    </div>
  </div>
</div>

<LinkModal
  bind:open={linkModalOpen}
  initialTitle={linkModalInitialTitle}
  initialUrl={linkModalInitialUrl}
  oninsert={handleLinkInsert}
/>

<style>
  .toolbar-wrapper {
    position: relative;
    flex: 0 0 auto;
    height: 44px;
    padding: 0.5rem var(--page-padding, 48px);
    border-top: 1px solid var(--border-light, #e5e5e5);
    border-bottom: 1px solid var(--border-light, #e5e5e5);
    box-sizing: border-box;
  }

  .toolbar {
    max-width: var(--max-content-width, 900px);
    margin: 0 auto;
    padding-left: 8px;
  }

  .toolbar-container {
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }

  .toolbar-btn {
    cursor: pointer;
    border: 0;
    background-color: transparent;
    transition: background 0.15s;
    height: 28px;
    width: 28px;
    padding: 4px;
    color: var(--text-secondary, #6b7280);
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .toolbar-btn:hover {
    background: rgba(55, 53, 47, 0.08);
    color: var(--text-primary, #1f2937);
  }

  .toolbar-btn :global(svg) {
    width: 18px;
    height: 18px;
  }

  .toolbar-btn-text {
    font-weight: 600;
    font-size: 12px;
    min-width: 28px;
  }

  .toolbar-separator {
    width: 1px;
    height: 18px;
    background: var(--border-light, #e5e5e5);
    margin: 0 0.25rem;
  }

  .toolbar-dropdown {
    position: relative;
    display: inline-block;
  }

  .dropdown-arrow {
    font-size: 10px;
    margin-left: 2px;
    opacity: 0.6;
  }

  .toolbar-dropdown-menu {
    position: absolute;
    top: 100%;
    left: 0;
    background: white;
    border: 1px solid var(--border-light, #e5e5e5);
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    min-width: 120px;
    z-index: 1000;
    padding: 4px 0;
    margin-top: 4px;
  }

  .toolbar-dropdown-menu button {
    display: block;
    width: 100%;
    padding: 6px 12px;
    text-align: left;
    background: none;
    border: none;
    cursor: pointer;
    font-size: 13px;
    color: var(--text-primary, #1f2937);
  }

  .toolbar-dropdown-menu button:hover {
    background: rgba(55, 53, 47, 0.08);
  }

  /* Overflow menu styles */
  .toolbar-overflow-menu {
    right: 0;
    left: auto;
    min-width: 180px;
  }

  .toolbar-overflow-menu button {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 8px 12px;
  }

  .overflow-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    flex-shrink: 0;
  }

  .overflow-icon :global(svg) {
    width: 16px;
    height: 16px;
  }

  .overflow-separator {
    height: 1px;
    background: var(--border-light, #e5e5e5);
    margin: 4px 0;
  }

  .overflow-submenu {
    padding: 4px 0;
  }

  .overflow-label {
    display: block;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted, #9ca3af);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .overflow-submenu button {
    padding: 6px 12px 6px 24px;
  }
</style>
