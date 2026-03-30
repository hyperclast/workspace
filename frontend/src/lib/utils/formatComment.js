function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function countChar(str, ch) {
  let n = 0;
  for (let i = 0; i < str.length; i++) {
    if (str[i] === ch) n++;
  }
  return n;
}

/** Strip trailing punctuation and unbalanced closing parens from a URL. */
function cleanUrlTail(url) {
  let cleaned = url.replace(/[.,;:!?"']+$/, "");
  while (cleaned.endsWith(")") && countChar(cleaned, "(") < countChar(cleaned, ")")) {
    cleaned = cleaned.slice(0, -1);
  }
  return cleaned;
}

const LINK_ATTRS = 'class="comment-link" target="_blank" rel="noopener noreferrer"';

export function formatCommentBody(content) {
  const escaped = escapeHtml(content);
  return (
    escaped
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      // Markdown links — allow balanced parens inside the URL for Wikipedia etc.
      .replace(
        /\[(.*?)\]\((https?:\/\/(?:[^\s()]|\([^\s()]*\))*)\)/g,
        `<a ${LINK_ATTRS} href="$2">$1</a>`
      )
      // Bare URLs — skip <code>…</code> and <a>…</a> sections, then linkify
      .replace(
        /(<code>[\s\S]*?<\/code>|<a\s[\s\S]*?<\/a>)|((?:^|[^"'>]))(https?:\/\/[^\s<]+)/g,
        (match, skip, prefix, url) => {
          if (skip) return skip;
          const cleaned = cleanUrlTail(url);
          const suffix = url.slice(cleaned.length);
          return `${prefix}<a ${LINK_ATTRS} href="${cleaned}">${cleaned}</a>${suffix}`;
        }
      )
      .replace(/\n/g, "<br>")
  );
}
