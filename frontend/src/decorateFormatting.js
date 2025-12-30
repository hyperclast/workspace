import { Prec } from "@codemirror/state";
import { Decoration, ViewPlugin, WidgetType, keymap, EditorView } from "@codemirror/view";

const BOLD_REGEX = /\*\*(.+?)\*\*/g;
const UNDERLINE_REGEX = /__(.+?)__/g;
const INLINE_CODE_REGEX = /`([^`\n]+)`/g;
const HEADING_REGEX = /^(#{1,6})\s+(.*)$/;
const HR_REGEX = /^(\s*)(-{3,}|\*{3,}|_{3,})(\s*)$/;
const BULLET_REGEX = /^(\s*)- (.*)$/;
const ORDERED_REGEX = /^(\s*)(\d+)\. (.*)$/;
const LIST_REGEX = /^(\s*)(?:- |\d+\. )/;
const CHECKBOX_REGEX = /^(\s*)- \[([ xX])\] (.*)$/;
const BLOCKQUOTE_REGEX = /^(\s*)> (.*)$/;
const CODE_FENCE_REGEX = /^```(\w*)$/;

class HrWidget extends WidgetType {
  toDOM() {
    const hr = document.createElement("hr");
    hr.className = "format-hr";
    return hr;
  }
}

class BulletWidget extends WidgetType {
  toDOM() {
    const span = document.createElement("span");
    span.className = "format-bullet";
    span.textContent = "•";
    return span;
  }
}

class CheckboxWidget extends WidgetType {
  constructor(checked, pos) {
    super();
    this.checked = checked;
    this.pos = pos;
  }

  eq(other) {
    return other.checked === this.checked && other.pos === this.pos;
  }

  toDOM() {
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = this.checked;
    checkbox.className = "format-checkbox";
    checkbox.dataset.pos = this.pos;
    return checkbox;
  }

  ignoreEvent() {
    return false;
  }
}

export const decorateFormatting = ViewPlugin.fromClass(
  class {
    constructor(view) {
      this.decorations = this.computeDecorations(view);
    }

    update(update) {
      if (update.docChanged || update.viewportChanged || update.selectionSet) {
        this.decorations = this.computeDecorations(update.view);
      }
    }

    computeDecorations(view) {
      const builder = [];
      const { state } = view;
      const text = state.doc.toString();

      const cursorPos = state.selection.main.head;
      const cursorLine = state.doc.lineAt(cursorPos).number;

      const codeBlocks = [];
      let inCodeBlock = false;
      let codeBlockStart = null;

      for (let i = 1; i <= state.doc.lines; i++) {
        const line = state.doc.line(i);
        if (CODE_FENCE_REGEX.test(line.text)) {
          if (!inCodeBlock) {
            inCodeBlock = true;
            codeBlockStart = i;
          } else {
            codeBlocks.push({ start: codeBlockStart, end: i });
            inCodeBlock = false;
            codeBlockStart = null;
          }
        }
      }

      const isInCodeBlock = (lineNum) => {
        for (const block of codeBlocks) {
          if (lineNum >= block.start && lineNum <= block.end) {
            return block;
          }
        }
        return null;
      };

      for (let i = 1; i <= state.doc.lines; i++) {
        const line = state.doc.line(i);
        const cursorOnLine = cursorLine === i;

        const codeBlock = isInCodeBlock(i);
        if (codeBlock) {
          const isStartFence = i === codeBlock.start;
          const isEndFence = i === codeBlock.end;
          const isFirstContent = i === codeBlock.start + 1;
          const isLastContent = i === codeBlock.end - 1;
          const isSingleLine = codeBlock.end - codeBlock.start === 2;

          if (isStartFence || isEndFence) {
            if (!cursorOnLine) {
              builder.push(Decoration.replace({}).range(line.from, line.to));
            } else {
              builder.push(Decoration.line({ class: "format-code-fence" }).range(line.from));
            }
          } else {
            let blockClass = "format-code-block";
            if (isSingleLine || (isFirstContent && isLastContent)) {
              blockClass += " format-code-block-single";
            } else if (isFirstContent) {
              blockClass += " format-code-block-first";
            } else if (isLastContent) {
              blockClass += " format-code-block-last";
            } else {
              blockClass += " format-code-block-middle";
            }
            builder.push(Decoration.line({ class: blockClass }).range(line.from));
          }
          continue;
        }

        const hrMatch = line.text.match(HR_REGEX);
        if (hrMatch) {
          if (!cursorOnLine) {
            builder.push(Decoration.replace({ widget: new HrWidget() }).range(line.from, line.to));
          }
          continue;
        }

        const headingMatch = line.text.match(HEADING_REGEX);
        if (headingMatch) {
          const level = headingMatch[1].length;
          const hashEnd = line.from + headingMatch[1].length + 1;
          const showRawSyntax = cursorOnLine && cursorPos < hashEnd;

          if (!showRawSyntax) {
            builder.push(Decoration.replace({}).range(line.from, hashEnd));
          } else {
            builder.push(
              Decoration.mark({ class: "format-heading-syntax" }).range(line.from, hashEnd)
            );
          }

          if (line.to > hashEnd) {
            builder.push(
              Decoration.mark({ class: `format-heading format-h${level}` }).range(hashEnd, line.to)
            );
          }

          builder.push(
            Decoration.line({ class: `format-heading-line format-h${level}-line` }).range(line.from)
          );
          continue;
        }

        const checkboxMatch = line.text.match(CHECKBOX_REGEX);
        if (checkboxMatch) {
          const indent = checkboxMatch[1].length;
          const indentLevel = Math.floor(indent / 2);
          const checked = checkboxMatch[2].toLowerCase() === "x";
          const checkboxStart = line.from + indent;
          const checkboxEnd = checkboxStart + 6;
          const textStart = checkboxEnd;
          const showRawSyntax = cursorOnLine && cursorPos < checkboxEnd;

          if (!showRawSyntax) {
            if (indent > 0) {
              builder.push(Decoration.replace({}).range(line.from, line.from + indent));
            }
            builder.push(
              Decoration.replace({ widget: new CheckboxWidget(checked, checkboxStart) }).range(
                checkboxStart,
                checkboxEnd
              )
            );
          } else {
            builder.push(
              Decoration.mark({ class: "format-list-syntax" }).range(line.from, checkboxEnd)
            );
          }

          const indentClass =
            !showRawSyntax && indentLevel > 0 ? ` format-indent-${Math.min(indentLevel, 10)}` : "";
          const rawClass = showRawSyntax ? " format-list-raw" : "";
          builder.push(
            Decoration.line({
              class: `format-list-item format-checkbox-item${indentClass}${rawClass}`,
            }).range(line.from)
          );

          if (checked && line.to > textStart) {
            builder.push(
              Decoration.mark({ class: "format-checkbox-checked" }).range(textStart, line.to)
            );
          }
          continue;
        }

        const bulletMatch = line.text.match(BULLET_REGEX);
        if (bulletMatch) {
          const indent = bulletMatch[1].length;
          const indentLevel = Math.floor(indent / 2);
          const dashPos = line.from + indent;
          const syntaxEnd = dashPos + 2;
          const showRawSyntax = cursorOnLine && cursorPos < syntaxEnd;

          if (!showRawSyntax) {
            if (indent > 0) {
              builder.push(Decoration.replace({}).range(line.from, line.from + indent));
            }
            builder.push(
              Decoration.replace({ widget: new BulletWidget() }).range(dashPos, dashPos + 1)
            );
          } else {
            builder.push(
              Decoration.mark({ class: "format-list-syntax" }).range(line.from, syntaxEnd)
            );
          }

          const indentClass =
            !showRawSyntax && indentLevel > 0 ? ` format-indent-${Math.min(indentLevel, 10)}` : "";
          const rawClass = showRawSyntax ? " format-list-raw" : "";
          builder.push(
            Decoration.line({
              class: `format-list-item format-bullet-item${indentClass}${rawClass}`,
            }).range(line.from)
          );
          continue;
        }

        const orderedMatch = line.text.match(ORDERED_REGEX);
        if (orderedMatch) {
          const indent = orderedMatch[1].length;
          const indentLevel = Math.floor(indent / 2);
          const numberLength = orderedMatch[2].length;
          const syntaxEnd = line.from + indent + numberLength + 2;
          const showRawSyntax = cursorOnLine && cursorPos < syntaxEnd;

          if (!showRawSyntax) {
            if (indent > 0) {
              builder.push(Decoration.replace({}).range(line.from, line.from + indent));
            }
          } else {
            builder.push(
              Decoration.mark({ class: "format-list-syntax" }).range(line.from, syntaxEnd)
            );
          }

          const indentClass =
            !showRawSyntax && indentLevel > 0 ? ` format-indent-${Math.min(indentLevel, 10)}` : "";
          const rawClass = showRawSyntax ? " format-list-raw" : "";
          builder.push(
            Decoration.line({
              class: `format-list-item format-ordered-item${indentClass}${rawClass}`,
            }).range(line.from)
          );
          continue;
        }

        const blockquoteMatch = line.text.match(BLOCKQUOTE_REGEX);
        if (blockquoteMatch) {
          const indent = blockquoteMatch[1].length;
          const quoteStart = line.from + indent;

          if (!cursorOnLine) {
            builder.push(Decoration.replace({}).range(quoteStart, quoteStart + 2));
          }

          builder.push(Decoration.line({ class: "format-blockquote" }).range(line.from));
          continue;
        }
      }

      for (const match of text.matchAll(BOLD_REGEX)) {
        const start = match.index;
        const end = start + match[0].length;
        const innerStart = start + 2;
        const innerEnd = end - 2;

        const matchLine = state.doc.lineAt(start).number;
        const cursorOnLine = cursorLine === matchLine;

        if (!cursorOnLine) {
          builder.push(Decoration.replace({}).range(start, innerStart));
        }

        builder.push(Decoration.mark({ class: "format-bold" }).range(innerStart, innerEnd));

        if (!cursorOnLine) {
          builder.push(Decoration.replace({}).range(innerEnd, end));
        }
      }

      for (const match of text.matchAll(UNDERLINE_REGEX)) {
        const start = match.index;
        const end = start + match[0].length;
        const innerStart = start + 2;
        const innerEnd = end - 2;

        const matchLine = state.doc.lineAt(start).number;
        const cursorOnLine = cursorLine === matchLine;

        if (!cursorOnLine) {
          builder.push(Decoration.replace({}).range(start, innerStart));
        }

        builder.push(Decoration.mark({ class: "format-underline" }).range(innerStart, innerEnd));

        if (!cursorOnLine) {
          builder.push(Decoration.replace({}).range(innerEnd, end));
        }
      }

      for (const match of text.matchAll(INLINE_CODE_REGEX)) {
        const start = match.index;
        const end = start + match[0].length;

        if (isInCodeBlock(state.doc.lineAt(start).number)) continue;

        const innerStart = start + 1;
        const innerEnd = end - 1;

        const matchLine = state.doc.lineAt(start).number;
        const cursorOnLine = cursorLine === matchLine;

        if (!cursorOnLine) {
          builder.push(Decoration.replace({}).range(start, innerStart));
        }

        builder.push(Decoration.mark({ class: "format-inline-code" }).range(innerStart, innerEnd));

        if (!cursorOnLine) {
          builder.push(Decoration.replace({}).range(innerEnd, end));
        }
      }

      return Decoration.set(builder, true);
    }
  },
  {
    decorations: (v) => v.decorations,
  }
);

const OL_REGEX = /^(\s*)(\d+)\.\s/;

function findOrderedListBlock(state, aroundLine) {
  let blockStart = aroundLine;
  while (blockStart > 1) {
    const prevLine = state.doc.line(blockStart - 1);
    if (OL_REGEX.test(prevLine.text)) {
      blockStart--;
    } else {
      break;
    }
  }

  let blockEnd = aroundLine;
  while (blockEnd < state.doc.lines) {
    const nextLine = state.doc.line(blockEnd + 1);
    if (OL_REGEX.test(nextLine.text)) {
      blockEnd++;
    } else {
      break;
    }
  }

  return { blockStart, blockEnd };
}

function renumberOrderedList(view, aroundLine) {
  const { state } = view;
  const changes = [];

  const { blockStart, blockEnd } = findOrderedListBlock(state, aroundLine);
  if (blockStart > blockEnd) return [];

  const counters = new Map();
  let prevIndent = -1;

  for (let lineNum = blockStart; lineNum <= blockEnd; lineNum++) {
    const line = state.doc.line(lineNum);
    const match = line.text.match(OL_REGEX);
    if (!match) continue;

    const indent = match[1].length;
    const currentNum = match[2];

    if (indent <= prevIndent) {
      for (const [key] of counters) {
        if (key > indent) {
          counters.delete(key);
        }
      }
    }

    const prevCount = counters.get(indent) || 0;
    const newNum = prevCount + 1;
    counters.set(indent, newNum);

    if (currentNum !== String(newNum)) {
      const numStart = line.from + indent;
      const numEnd = numStart + currentNum.length;
      changes.push({ from: numStart, to: numEnd, insert: String(newNum) });
    }

    prevIndent = indent;
  }

  return changes;
}

function hasOrderedListInRange(state, startLine, endLine) {
  for (let lineNum = startLine; lineNum <= endLine; lineNum++) {
    const line = state.doc.line(lineNum);
    if (OL_REGEX.test(line.text)) {
      return lineNum;
    }
  }
  return null;
}

function handleListIndent(view) {
  const { state } = view;
  const { from, to } = state.selection.main;
  const line = state.doc.lineAt(from);

  if (!LIST_REGEX.test(line.text)) {
    return false;
  }

  if (from !== to) {
    const startLine = state.doc.lineAt(from);
    const endLine = state.doc.lineAt(to);
    const changes = [];

    for (let lineNum = startLine.number; lineNum <= endLine.number; lineNum++) {
      const l = state.doc.line(lineNum);
      if (LIST_REGEX.test(l.text)) {
        changes.push({ from: l.from, insert: "  " });
      }
    }

    if (changes.length > 0) {
      view.dispatch({ changes, userEvent: "indent" });

      const olLine = hasOrderedListInRange(view.state, startLine.number, endLine.number);
      if (olLine) {
        const renumberChanges = renumberOrderedList(view, olLine);
        if (renumberChanges.length > 0) {
          view.dispatch({ changes: renumberChanges, userEvent: "indent.renumber" });
        }
      }
    }
  } else {
    view.dispatch({
      changes: { from: line.from, insert: "  " },
      selection: { anchor: from + 2 },
      userEvent: "indent",
    });

    if (OL_REGEX.test(line.text)) {
      const renumberChanges = renumberOrderedList(view, line.number);
      if (renumberChanges.length > 0) {
        view.dispatch({ changes: renumberChanges, userEvent: "indent.renumber" });
      }
    }
  }

  return true;
}

function handleListUnindent(view) {
  const { state } = view;
  const { from, to } = state.selection.main;
  const line = state.doc.lineAt(from);

  if (!LIST_REGEX.test(line.text)) {
    return false;
  }

  if (from !== to) {
    const startLine = state.doc.lineAt(from);
    const endLine = state.doc.lineAt(to);
    const changes = [];

    for (let lineNum = startLine.number; lineNum <= endLine.number; lineNum++) {
      const l = state.doc.line(lineNum);
      if (LIST_REGEX.test(l.text)) {
        const spaces = l.text.match(/^(\s*)/)[1];
        const removeCount = Math.min(2, spaces.length);
        if (removeCount > 0) {
          changes.push({ from: l.from, to: l.from + removeCount, insert: "" });
        }
      }
    }

    if (changes.length > 0) {
      view.dispatch({ changes, userEvent: "indent" });

      const olLine = hasOrderedListInRange(view.state, startLine.number, endLine.number);
      if (olLine) {
        const renumberChanges = renumberOrderedList(view, olLine);
        if (renumberChanges.length > 0) {
          view.dispatch({ changes: renumberChanges, userEvent: "indent.renumber" });
        }
      }
    }
  } else {
    const spaces = line.text.match(/^(\s*)/)[1];
    const removeCount = Math.min(2, spaces.length);

    if (removeCount > 0) {
      view.dispatch({
        changes: { from: line.from, to: line.from + removeCount, insert: "" },
        selection: { anchor: Math.max(line.from, from - removeCount) },
        userEvent: "indent",
      });

      if (OL_REGEX.test(line.text)) {
        const renumberChanges = renumberOrderedList(view, line.number);
        if (renumberChanges.length > 0) {
          view.dispatch({ changes: renumberChanges, userEvent: "indent.renumber" });
        }
      }
    }
  }

  return true;
}

export function toggleCheckbox(view) {
  const { state } = view;
  const line = state.doc.lineAt(state.selection.main.head);
  const match = line.text.match(CHECKBOX_REGEX);

  if (match) {
    const indent = match[1].length;
    const currentState = match[2];
    const newState = currentState === " " ? "x" : " ";
    const bracketPos = line.from + indent + 3;

    view.dispatch({
      changes: { from: bracketPos, to: bracketPos + 1, insert: newState },
    });
    return true;
  }

  const bulletMatch = line.text.match(BULLET_REGEX);
  if (bulletMatch) {
    const indent = bulletMatch[1].length;
    const insertPos = line.from + indent + 2;
    view.dispatch({
      changes: { from: insertPos, insert: "[ ] " },
      selection: { anchor: state.selection.main.head + 4 },
    });
    return true;
  }

  const insertText = "- [ ] ";
  view.dispatch({
    changes: { from: line.from, insert: insertText },
    selection: { anchor: state.selection.main.head + insertText.length },
  });
  return true;
}

export const checkboxClickHandler = EditorView.domEventHandlers({
  click(event, view) {
    const target = event.target;
    if (target.classList.contains("format-checkbox")) {
      event.preventDefault();
      const pos = parseInt(target.dataset.pos, 10);
      const line = view.state.doc.lineAt(pos);
      const match = line.text.match(CHECKBOX_REGEX);
      if (match) {
        const indent = match[1].length;
        const currentState = match[2];
        const newState = currentState === " " ? "x" : " ";
        const bracketPos = line.from + indent + 3;
        view.dispatch({
          changes: { from: bracketPos, to: bracketPos + 1, insert: newState },
        });
      }
      return true;
    }
    return false;
  },
});

const EMPTY_BLOCKQUOTE_REGEX = /^(\s*)>\s*$/;

function handleBlockquoteEnter(view) {
  const { state } = view;
  const { from } = state.selection.main;
  const line = state.doc.lineAt(from);

  const emptyMatch = line.text.match(EMPTY_BLOCKQUOTE_REGEX);
  if (emptyMatch) {
    const indent = emptyMatch[1];
    view.dispatch({
      changes: { from: line.from, to: line.to, insert: indent },
      selection: { anchor: line.from + indent.length },
    });
    return true;
  }

  const match = line.text.match(BLOCKQUOTE_REGEX);
  if (match) {
    const indent = match[1];
    const newLine = "\n" + indent + "> ";
    view.dispatch({
      changes: { from, insert: newLine },
      selection: { anchor: from + newLine.length },
    });
    return true;
  }

  return false;
}

function handleBlockquoteShiftEnter(view) {
  const { state } = view;
  const { from } = state.selection.main;
  const line = state.doc.lineAt(from);

  const match = line.text.match(BLOCKQUOTE_REGEX) || line.text.match(EMPTY_BLOCKQUOTE_REGEX);
  if (match) {
    view.dispatch({
      changes: { from, insert: "\n" },
      selection: { anchor: from + 1 },
    });
    return true;
  }

  return false;
}

export const listKeymap = Prec.high(
  keymap.of([
    {
      key: "Tab",
      run: handleListIndent,
    },
    {
      key: "Shift-Tab",
      run: handleListUnindent,
    },
    {
      key: "Mod-l",
      run: toggleCheckbox,
    },
  ])
);

export const blockquoteKeymap = Prec.highest(
  keymap.of([
    {
      key: "Enter",
      run: handleBlockquoteEnter,
    },
    {
      key: "Shift-Enter",
      run: handleBlockquoteShiftEnter,
    },
  ])
);
