import { EditorSelection, Prec } from "@codemirror/state";
import { keymap } from "@codemirror/view";

// Skips leading whitespace and any chain of markdown line-prefix markers:
// bullet (-,*,+) with optional [ ]/[x]/[X] checkbox, numbered list (1.),
// ATX heading (#..######), or blockquote (>). Each marker must be followed
// by whitespace. Stops at the first content character.
const SMART_HOME_PREFIX = /^\s*(?:(?:[-*+]\s+(?:\[[ xX]\]\s+)?|\d+\.\s+|#{1,6}\s+|>\s+))*/;

export function smartHomePosition(lineText) {
  const match = lineText.match(SMART_HOME_PREFIX);
  return match ? match[0].length : 0;
}

function moveSmartHome(view, extend) {
  const { state } = view;
  const ranges = state.selection.ranges.map((range) => {
    const line = state.doc.lineAt(range.head);
    const target = line.from + smartHomePosition(line.text);
    return extend ? EditorSelection.range(range.anchor, target) : EditorSelection.cursor(target);
  });
  view.dispatch({
    selection: EditorSelection.create(ranges, state.selection.mainIndex),
    scrollIntoView: true,
    userEvent: "select",
  });
  return true;
}

export const cursorSmartHomeLeft = (view) => moveSmartHome(view, false);
export const selectSmartHomeLeft = (view) => moveSmartHome(view, true);

export const smartHomeKeymap = Prec.high(
  keymap.of([
    {
      mac: "Cmd-ArrowLeft",
      run: cursorSmartHomeLeft,
      shift: selectSmartHomeLeft,
      preventDefault: true,
    },
  ])
);
