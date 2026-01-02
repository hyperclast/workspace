<script>
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
    Redo2
  } from "lucide-static";
  import { openSidebar, setActiveTab } from "../stores/sidebar.svelte.js";
  import { toggleCheckbox } from "../../decorateFormatting.js";
  import LinkModal from "./LinkModal.svelte";

  let { editorView = $bindable(null), tableUtils = null } = $props();

  let headingMenuOpen = $state(false);
  let linkModalOpen = $state(false);
  let linkModalInitialTitle = $state('');
  let linkModalInitialUrl = $state('');
  let linkInsertPosition = $state({ from: 0, to: 0 });
  let linkEditMode = $state(false);

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

  function handleClickOutside(event) {
    if (headingMenuOpen && !event.target.closest('.toolbar-dropdown')) {
      headingMenuOpen = false;
    }
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
</script>

<svelte:document onclick={handleClickOutside} />

<div class="toolbar-wrapper">
  <div class="toolbar">
    <div class="toolbar-container">
      <button class="toolbar-btn" title="Undo (Cmd+Z)" onmousedown={(e) => { e.preventDefault(); handleUndo(); }}>
        {@html Undo2}
      </button>
      <button class="toolbar-btn" title="Redo (Cmd+Shift+Z)" onmousedown={(e) => { e.preventDefault(); handleRedo(); }}>
        {@html Redo2}
      </button>

      <span class="toolbar-separator"></span>

      <button class="toolbar-btn" title="Bold (Cmd+B)" onmousedown={(e) => { e.preventDefault(); toggleFormat("**"); }}>
        {@html Bold}
      </button>
      <button class="toolbar-btn" title="Italic (Cmd+I)" onmousedown={(e) => { e.preventDefault(); toggleFormat("*"); }}>
        {@html Italic}
      </button>
      <button class="toolbar-btn" title="Underline (Cmd+U)" onmousedown={(e) => { e.preventDefault(); toggleFormat("__"); }}>
        {@html Underline}
      </button>
      <button class="toolbar-btn" title="Strikethrough" onmousedown={(e) => { e.preventDefault(); toggleFormat("~~"); }}>
        {@html Strikethrough}
      </button>
      <button class="toolbar-btn" title="Inline code" onmousedown={(e) => { e.preventDefault(); toggleFormat("`"); }}>
        {@html Code}
      </button>
      <button class="toolbar-btn" title="Code block" onmousedown={(e) => { e.preventDefault(); insertCodeBlock(); }}>
        {@html FileCode}
      </button>
      <button class="toolbar-btn" title="Insert link (Cmd+K)" onmousedown={(e) => { e.preventDefault(); insertLink(); }}>
        {@html Link2}
      </button>

      <span class="toolbar-separator"></span>

      <button class="toolbar-btn toolbar-btn-text" title="Heading 2" onmousedown={(e) => { e.preventDefault(); toggleLinePrefix("## "); }}>
        H2
      </button>
      <button class="toolbar-btn toolbar-btn-text" title="Heading 3" onmousedown={(e) => { e.preventDefault(); toggleLinePrefix("### "); }}>
        H3
      </button>
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

      <span class="toolbar-separator"></span>

      <button class="toolbar-btn" title="Bullet list" onmousedown={(e) => { e.preventDefault(); toggleLinePrefix("- "); }}>
        {@html List}
      </button>
      <button class="toolbar-btn" title="Numbered list" onmousedown={(e) => { e.preventDefault(); toggleOrderedList(); }}>
        {@html ListOrdered}
      </button>
      <button class="toolbar-btn" title="Checklist (Cmd+L)" onmousedown={(e) => { e.preventDefault(); if (editorView) toggleCheckbox(editorView); }}>
        {@html CheckSquare}
      </button>
      <button class="toolbar-btn" title="Blockquote" onmousedown={(e) => { e.preventDefault(); toggleLinePrefix("> "); }}>
        {@html Quote}
      </button>

      <span class="toolbar-separator"></span>

      <button class="toolbar-btn" title="Fold all sections" onmousedown={(e) => { e.preventDefault(); handleFoldAll(); }}>
        {@html ChevronsDownUp}
      </button>
      <button class="toolbar-btn" title="Expand all sections" onmousedown={(e) => { e.preventDefault(); handleUnfoldAll(); }}>
        {@html ChevronsUpDown}
      </button>
      <button class="toolbar-btn" title="Ask AI" onmousedown={(e) => { e.preventDefault(); openAskTab(); }}>
        {@html Search}
      </button>
      <button class="toolbar-btn" title="Insert table" onmousedown={(e) => { e.preventDefault(); insertTable(); }}>
        {@html Table2}
      </button>
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
</style>
