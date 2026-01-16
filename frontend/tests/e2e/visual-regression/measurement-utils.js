/**
 * DOM Measurement Utilities for Visual Regression Testing
 *
 * These functions run in the browser context via page.evaluate() and provide
 * algorithmic proof of alignment and spacing rather than visual guessing.
 */

/**
 * Get bounding rectangles for all elements matching a selector,
 * relative to the editor container.
 */
export function getBoundingRects(selector, containerSelector = ".cm-content") {
  return `
    (() => {
      const container = document.querySelector("${containerSelector}");
      if (!container) return { error: "Container not found" };

      const containerRect = container.getBoundingClientRect();
      const elements = container.querySelectorAll("${selector}");

      return Array.from(elements).map((el, idx) => {
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return {
          index: idx,
          left: rect.left - containerRect.left,
          top: rect.top - containerRect.top,
          right: rect.right - containerRect.left,
          bottom: rect.bottom - containerRect.top,
          width: rect.width,
          height: rect.height,
          paddingLeft: parseFloat(style.paddingLeft),
          marginLeft: parseFloat(style.marginLeft),
          className: el.className,
          text: el.textContent?.slice(0, 50)
        };
      });
    })()
  `;
}

/**
 * Measure vertical spacing between consecutive elements.
 */
export function measureVerticalSpacing(selector) {
  return `
    (() => {
      const elements = document.querySelectorAll("${selector}");
      const spacings = [];

      for (let i = 1; i < elements.length; i++) {
        const prevRect = elements[i - 1].getBoundingClientRect();
        const currRect = elements[i].getBoundingClientRect();
        spacings.push({
          fromIndex: i - 1,
          toIndex: i,
          spacing: currRect.top - prevRect.bottom,
          prevText: elements[i - 1].textContent?.slice(0, 30),
          currText: elements[i].textContent?.slice(0, 30)
        });
      }

      return spacings;
    })()
  `;
}

/**
 * Get left edge positions for alignment verification.
 */
export function getLeftEdgePositions(selector) {
  return `
    (() => {
      const elements = document.querySelectorAll("${selector}");
      const container = document.querySelector(".cm-content");
      const containerLeft = container?.getBoundingClientRect().left || 0;

      return Array.from(elements).map((el, idx) => {
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return {
          index: idx,
          absoluteLeft: rect.left,
          relativeLeft: rect.left - containerLeft,
          paddingLeft: parseFloat(style.paddingLeft),
          marginLeft: parseFloat(style.marginLeft),
          textIndent: parseFloat(style.textIndent) || 0,
          className: el.className,
          text: el.textContent?.slice(0, 30)
        };
      });
    })()
  `;
}

/**
 * Measure line heights for all visible lines.
 */
export function measureLineHeights() {
  return `
    (() => {
      const lines = document.querySelectorAll(".cm-line");
      return Array.from(lines).map((line, idx) => {
        const style = getComputedStyle(line);
        const rect = line.getBoundingClientRect();
        return {
          index: idx,
          lineHeight: style.lineHeight,
          lineHeightPx: parseFloat(style.lineHeight) || null,
          fontSize: parseFloat(style.fontSize),
          computedHeight: rect.height,
          className: line.className,
          hasFormat: line.className.includes("format-"),
          text: line.textContent?.slice(0, 30)
        };
      });
    })()
  `;
}

/**
 * Measure link styling properties.
 */
export function measureLinkStyles() {
  return `
    (() => {
      const links = document.querySelectorAll(".format-link");
      return Array.from(links).map((link, idx) => {
        const style = getComputedStyle(link);
        const rect = link.getBoundingClientRect();
        return {
          index: idx,
          textDecoration: style.textDecoration,
          textDecorationLine: style.textDecorationLine,
          textDecorationColor: style.textDecorationColor,
          textDecorationStyle: style.textDecorationStyle,
          color: style.color,
          fontWeight: style.fontWeight,
          isInternal: link.classList.contains("format-link-internal"),
          isExternal: link.classList.contains("format-link-external"),
          height: rect.height,
          text: link.textContent
        };
      });
    })()
  `;
}

/**
 * Measure table column alignment.
 */
export function measureTableColumns() {
  return `
    (() => {
      const tableRows = document.querySelectorAll(".cm-line.cm-table-header, .cm-line.cm-table-row, .cm-line.cm-table-separator");
      const container = document.querySelector(".cm-content");
      const containerLeft = container?.getBoundingClientRect().left || 0;

      return Array.from(tableRows).map((row, rowIdx) => {
        const rect = row.getBoundingClientRect();
        const style = getComputedStyle(row);

        // Find all pipe characters in the row text and their positions
        const text = row.textContent || "";
        const pipePositions = [];
        for (let i = 0; i < text.length; i++) {
          if (text[i] === "|") {
            pipePositions.push(i);
          }
        }

        return {
          rowIndex: rowIdx,
          left: rect.left - containerLeft,
          width: rect.width,
          height: rect.height,
          className: row.className,
          pipeCount: pipePositions.length,
          text: text.slice(0, 50)
        };
      });
    })()
  `;
}

/**
 * Get indent level data for nested elements.
 */
export function measureIndentLevels() {
  return `
    (() => {
      const items = document.querySelectorAll('.cm-line[class*="format-indent-"], .cm-line.format-bullet-item:not([class*="format-indent"]), .cm-line.format-checkbox-item:not([class*="format-indent"]), .cm-line.format-ordered-item:not([class*="format-indent"])');
      const container = document.querySelector(".cm-content");
      const containerLeft = container?.getBoundingClientRect().left || 0;

      return Array.from(items).map((item, idx) => {
        const indentMatch = item.className.match(/format-indent-(\\d+)/);
        const indentLevel = indentMatch ? parseInt(indentMatch[1]) : 0;
        const rect = item.getBoundingClientRect();
        const style = getComputedStyle(item);

        return {
          index: idx,
          indentLevel,
          paddingLeft: parseFloat(style.paddingLeft),
          left: rect.left - containerLeft,
          className: item.className.split(" ").filter(c => c.includes("format")).join(" "),
          text: item.textContent?.slice(0, 30)
        };
      });
    })()
  `;
}

/**
 * Measure element heights grouped by type.
 */
export function measureElementHeightsByType() {
  return `
    (() => {
      const lines = document.querySelectorAll(".cm-line");
      const data = [];

      for (const line of lines) {
        const rect = line.getBoundingClientRect();
        const style = getComputedStyle(line);

        // Determine line type
        let type = "paragraph";
        if (line.className.includes("format-h")) type = "heading";
        else if (line.className.includes("format-bullet")) type = "bullet";
        else if (line.className.includes("format-ordered")) type = "ordered";
        else if (line.className.includes("format-checkbox")) type = "checkbox";
        else if (line.className.includes("format-blockquote")) type = "blockquote";
        else if (line.className.includes("format-code")) type = "code";
        else if (!line.textContent?.trim()) type = "empty";

        data.push({
          type,
          height: rect.height,
          lineHeight: style.lineHeight,
          fontSize: parseFloat(style.fontSize),
          className: line.className,
          text: line.textContent?.slice(0, 20)
        });
      }

      return data;
    })()
  `;
}

/**
 * Get text start position (where actual text begins, not element edge).
 */
export function getTextStartPositions(selector) {
  return `
    (() => {
      const elements = document.querySelectorAll("${selector}");
      const container = document.querySelector(".cm-content");
      const containerLeft = container?.getBoundingClientRect().left || 0;

      const getTextStartX = (el) => {
        const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
        let node;
        while (node = walker.nextNode()) {
          if (node.textContent.trim()) {
            const range = document.createRange();
            const trimStart = node.textContent.search(/\\S/);
            if (trimStart >= 0 && trimStart < node.textContent.length) {
              range.setStart(node, trimStart);
              range.setEnd(node, trimStart + 1);
              return range.getBoundingClientRect().left - containerLeft;
            }
          }
        }
        return el.getBoundingClientRect().left - containerLeft;
      };

      return Array.from(elements).map((el, idx) => ({
        index: idx,
        textStartX: getTextStartX(el),
        elementLeft: el.getBoundingClientRect().left - containerLeft,
        className: el.className,
        text: el.textContent?.slice(0, 30)
      }));
    })()
  `;
}
