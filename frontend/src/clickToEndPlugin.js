import { ViewPlugin } from "@codemirror/view";

export const clickToEndPlugin = ViewPlugin.define((view) => {
  const editorContainer = document.getElementById("editor");

  const containerHandler = (e) => {
    if (e.target !== editorContainer) {
      return;
    }

    const doc = view.state.doc;
    const lastPos = doc.length;

    e.preventDefault();
    requestAnimationFrame(() => {
      view.dispatch({
        selection: { anchor: lastPos },
        scrollIntoView: true,
      });
      view.focus();
    });
  };

  const editorHandler = (e) => {
    const doc = view.state.doc;
    const lastPos = doc.length;
    const lastCoords = view.coordsAtPos(lastPos);

    if (!lastCoords) return;

    if (e.clientY > lastCoords.bottom) {
      requestAnimationFrame(() => {
        view.dispatch({
          selection: { anchor: lastPos },
          scrollIntoView: true,
        });
        view.focus();
      });
    }
  };

  editorContainer?.addEventListener("mousedown", containerHandler);
  view.dom.addEventListener("mousedown", editorHandler);

  return {
    destroy() {
      editorContainer?.removeEventListener("mousedown", containerHandler);
      view.dom.removeEventListener("mousedown", editorHandler);
    },
  };
});
