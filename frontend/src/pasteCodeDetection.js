import { EditorView } from "@codemirror/view";
import { codeFenceField } from "./decorateFormatting.js";
import { initModals } from "./lib/modal.js";
import { openCodePaste } from "./lib/stores/modal.svelte.js";

/**
 * Language-specific keyword patterns for code detection.
 * Each pattern adds +30 to the confidence score.
 */
const LANGUAGE_PATTERNS = {
  py: /^(def|class|import|from|if|elif|else|for|while|try|except|return|raise|with|async|await|lambda|yield)\s/m,
  js: /^(const|let|var|function|class|import|export|async|await|return|throw|if|else|for|while|try|catch)\s/m,
  ts: /^(const|let|var|function|class|import|export|async|await|return|throw|if|else|for|while|try|catch|interface|type|enum)\s/m,
  sql: /^(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|FROM|WHERE|JOIN|INNER|LEFT|RIGHT|GROUP|ORDER|HAVING|UNION|INDEX|TABLE|INTO)\s/im,
  html: /^<(!DOCTYPE|html|head|body|div|span|script|style|link|meta|form|input|button|a|p|h[1-6]|ul|ol|li|table|tr|td|th|img|svg|nav|header|footer|section|article|main)/im,
  sh: /^(#!\/|if\s+\[\[?|then|fi|elif|else|case|esac|for|do|done|while|function|export|source|echo|cd|ls|rm|cp|mv|mkdir|chmod|chown|grep|sed|awk|curl|wget)\s?/m,
  go: /^(func|package|import|type|struct|interface|var|const|if|else|for|range|switch|case|default|return|defer|go|chan|map)\s/m,
  rust: /^(fn|impl|struct|enum|pub|use|mod|trait|let|mut|const|if|else|for|while|loop|match|return|async|await)\s/m,
  java: /^(public|private|protected|class|interface|enum|void|int|long|double|float|boolean|String|static|final|abstract|extends|implements|return|if|else|for|while|try|catch|throw|new)\s/m,
  kotlin:
    /^(fun|val|var|class|object|interface|sealed|data|enum|when|if|else|for|while|return|throw|try|catch|import|package|suspend|inline|companion)\s/m,
  c: /^(#include|#define|#ifdef|#ifndef|int|void|char|float|double|long|short|unsigned|signed|struct|union|enum|typedef|return|if|else|for|while|switch|case|break|continue)\s/m,
  cpp: /^(#include|#define|class|public|private|protected|virtual|template|typename|namespace|using|std::|vector|string|int|void|char|float|double|return|if|else|for|while|new|delete)\s/m,
  css: /^(\.|#|@media|@import|@keyframes|@font-face|:root|\*|body|html|div|span|a|p|h[1-6])\s*\{/m,
  json: /^\s*[\[{]/m,
  ruby: /^(def|class|module|require|include|extend|attr_|if|elsif|else|unless|case|when|for|while|do|end|return|yield|lambda|proc)\s/m,
  php: /^(<\?php|\$[a-zA-Z_]|function|class|public|private|protected|namespace|use|echo|print|return|if|else|elseif|for|foreach|while)\s?/m,
  xml: /^<(\?xml|!DOCTYPE|[a-zA-Z][\w:-]*(\s|>|$))/m,
  lisp: /^(\(defun|\(defmacro|\(defvar|\(defparameter|\(let|\(let\*|\(lambda|\(if|\(cond|\(when|\(unless|\(loop|\(setq|\(setf)/m,
};

/**
 * Structural patterns that indicate code.
 */
const STRUCTURAL_PATTERNS = {
  // Lines ending with semicolons (but not natural language like "e.g.;")
  semicolonEndings: /;\s*$/m,
  // Function calls: word followed by parentheses
  functionCalls: /\b[a-zA-Z_]\w*\s*\([^)]*\)/,
  // Code operators
  codeOperators: /(=>|===|!==|&&|\|\||::|\->|\.\.\.|\+=|-=|\*=|\/=|%=|\+\+|--|<<|>>)/,
  // Assignment with type annotations
  typeAnnotations:
    /:\s*(string|number|boolean|int|float|void|any|null|undefined|Array|Object|Promise|Map|Set)\b/,
  // Object/array literals
  objectLiterals: /\{\s*['"a-zA-Z_]\w*['"]?\s*:/,
  // Arrow functions
  arrowFunctions: /\([^)]*\)\s*=>/,
  // Method chaining
  methodChaining: /\.\w+\([^)]*\)\.\w+\(/,
  // Import/require statements
  importStatements: /^(import|require|from|using|include)\s+/m,
  // Variable declarations
  varDeclarations: /^(const|let|var|int|float|double|char|string|bool|void)\s+\w+\s*=/m,
};

/**
 * Common prose words that indicate natural language.
 * High frequency of these words suggests the text is NOT code.
 */
const PROSE_WORDS = [
  "the",
  "and",
  "is",
  "are",
  "was",
  "were",
  "be",
  "been",
  "being",
  "have",
  "has",
  "had",
  "do",
  "does",
  "did",
  "will",
  "would",
  "could",
  "should",
  "may",
  "might",
  "must",
  "can",
  "this",
  "that",
  "these",
  "those",
  "what",
  "which",
  "who",
  "whom",
  "whose",
  "when",
  "where",
  "why",
  "how",
  "all",
  "each",
  "every",
  "both",
  "few",
  "more",
  "most",
  "other",
  "some",
  "such",
  "only",
  "own",
  "same",
  "than",
  "very",
  "just",
  "also",
  "now",
  "here",
  "there",
  "then",
  "so",
  "because",
  "although",
  "however",
  "therefore",
  "thus",
  "hence",
  "furthermore",
  "moreover",
  "nevertheless",
  "meanwhile",
  "consequently",
];

/**
 * Calculate a confidence score for whether text looks like code.
 * Score >= 40 indicates likely code.
 *
 * @param {string} text - The text to analyze
 * @returns {boolean} - True if the text appears to be code
 */
export function looksLikeCode(text) {
  if (!text || typeof text !== "string") return false;

  // Skip very short or single-line pastes
  const trimmed = text.trim();
  if (trimmed.length < 20) return false;

  // For large pastes, only analyze the first 50 lines
  const lines = trimmed.split("\n");
  const linesToAnalyze = lines.slice(0, 50).join("\n");

  let score = 0;

  // Check for language-specific keywords (+30 each, max +60)
  let keywordMatches = 0;
  for (const pattern of Object.values(LANGUAGE_PATTERNS)) {
    if (pattern.test(linesToAnalyze)) {
      keywordMatches++;
      if (keywordMatches >= 2) break;
    }
  }
  score += keywordMatches * 30;

  // Check for structural patterns (+10-15 each)
  if (STRUCTURAL_PATTERNS.semicolonEndings.test(linesToAnalyze)) score += 15;
  if (STRUCTURAL_PATTERNS.functionCalls.test(linesToAnalyze)) score += 10;
  if (STRUCTURAL_PATTERNS.codeOperators.test(linesToAnalyze)) score += 15;
  if (STRUCTURAL_PATTERNS.typeAnnotations.test(linesToAnalyze)) score += 15;
  if (STRUCTURAL_PATTERNS.objectLiterals.test(linesToAnalyze)) score += 10;
  if (STRUCTURAL_PATTERNS.arrowFunctions.test(linesToAnalyze)) score += 15;
  if (STRUCTURAL_PATTERNS.methodChaining.test(linesToAnalyze)) score += 10;
  if (STRUCTURAL_PATTERNS.importStatements.test(linesToAnalyze)) score += 20;
  if (STRUCTURAL_PATTERNS.varDeclarations.test(linesToAnalyze)) score += 15;

  // Check for consistent indentation (+20)
  if (hasConsistentIndentation(lines.slice(0, 50))) {
    score += 20;
  }

  // Check for prose words (-20 if high frequency)
  const proseWordCount = countProseWords(linesToAnalyze.toLowerCase());
  const wordCount = linesToAnalyze.split(/\s+/).length;
  const proseRatio = wordCount > 0 ? proseWordCount / wordCount : 0;

  if (proseRatio > 0.15) {
    score -= 20;
  }
  if (proseRatio > 0.25) {
    score -= 20;
  }

  // Check for JSON (common paste)
  if (/^\s*[\[{]/.test(trimmed) && /[\]}]\s*$/.test(trimmed)) {
    try {
      JSON.parse(trimmed);
      score += 40; // Valid JSON is definitely code
    } catch {
      // Not valid JSON, continue with normal scoring
    }
  }

  return score >= 40;
}

/**
 * Check if lines have consistent indentation (2-space, 4-space, or tab).
 */
function hasConsistentIndentation(lines) {
  const indentedLines = lines.filter((line) => /^[\t ]+\S/.test(line));
  if (indentedLines.length < 3) return false;

  // Check for consistent indentation pattern
  const indents = indentedLines.map((line) => {
    const match = line.match(/^([\t ]+)/);
    return match ? match[1] : "";
  });

  // Check if most indents are multiples of 2 or 4 spaces, or tabs
  let consistentCount = 0;
  for (const indent of indents) {
    if (/^\t+$/.test(indent)) {
      consistentCount++;
    } else if (/^( {2})+$/.test(indent) || /^( {4})+$/.test(indent)) {
      consistentCount++;
    }
  }

  return consistentCount / indents.length > 0.7;
}

/**
 * Count occurrences of common prose words.
 */
function countProseWords(text) {
  let count = 0;
  const words = text.split(/\s+/);
  for (const word of words) {
    // Remove punctuation for comparison
    const cleanWord = word.replace(/[.,;:!?'"()[\]{}]/g, "");
    if (PROSE_WORDS.includes(cleanWord)) {
      count++;
    }
  }
  return count;
}

/**
 * Detect the programming language of code text.
 * Returns the language code (e.g., 'py', 'js') or empty string if uncertain.
 *
 * @param {string} text - The code text to analyze
 * @returns {string} - Language code or empty string
 */
export function detectLanguage(text) {
  if (!text || typeof text !== "string") return "";

  const trimmed = text.trim();

  // Check in order of distinctiveness

  // Shebang
  if (/^#!/.test(trimmed)) {
    if (/#!.*python/.test(trimmed)) return "py";
    if (/#!.*node/.test(trimmed)) return "js";
    if (/#!.*ruby/.test(trimmed)) return "ruby";
    return "sh";
  }

  // HTML/XML documents
  if (/^<!DOCTYPE\s+html/i.test(trimmed)) return "html";
  if (/^<\?xml/i.test(trimmed)) return "xml";
  if (/^<html/i.test(trimmed)) return "html";

  // JSON
  if (/^\s*[\[{]/.test(trimmed) && /[\]}]\s*$/.test(trimmed)) {
    try {
      JSON.parse(trimmed);
      return "json";
    } catch {
      // Not valid JSON
    }
  }

  // SQL (case insensitive, starts with SQL keyword)
  if (/^(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|WITH)\s/i.test(trimmed)) {
    return "sql";
  }

  // PHP
  if (/^<\?php/i.test(trimmed)) return "php";

  // Python-specific (def/class with colon, no braces)
  if (/^(def|class)\s+\w+.*:$/m.test(trimmed) && !/\{/.test(trimmed)) {
    return "py";
  }
  if (/^(import|from)\s+\w+/.test(trimmed) && !/[{};]/.test(trimmed)) {
    return "py";
  }

  // Ruby-specific (def without parentheses, end keyword)
  if (/^def\s+\w+\s*\n/.test(trimmed) && /\bend\b/.test(trimmed)) {
    return "ruby";
  }
  if (/^(require|include|module)\s+['"]/.test(trimmed)) {
    return "ruby";
  }

  // Lisp-specific (parentheses-heavy, defun/defmacro)
  if (/^\(defun\s+/.test(trimmed)) return "lisp";
  if (/^\(defmacro\s+/.test(trimmed)) return "lisp";
  if (/^\(lambda\s+/.test(trimmed) && /\(/.test(trimmed.slice(7))) return "lisp";

  // Go-specific
  if (/^package\s+\w+/.test(trimmed)) return "go";
  if (/^func\s+\w+.*\{/.test(trimmed)) return "go";

  // Rust-specific
  if (/^fn\s+\w+.*->/.test(trimmed)) return "rust";
  if (/^(use|mod|impl|struct|enum)\s+/.test(trimmed) && /;$/.test(trimmed)) {
    return "rust";
  }

  // Java-specific
  if (/^(public|private|protected)\s+(class|interface|enum)\s/.test(trimmed)) {
    return "java";
  }

  // Kotlin-specific (fun keyword, val/var without type prefix)
  if (/^fun\s+\w+/.test(trimmed)) return "kotlin";
  if (/^(val|var)\s+\w+\s*[=:]/.test(trimmed) && /\{/.test(trimmed)) {
    return "kotlin";
  }
  if (/^(data\s+class|sealed\s+class|object\s+\w+)/.test(trimmed)) {
    return "kotlin";
  }

  // C/C++ specific
  if (/^#include\s*[<"]/.test(trimmed)) {
    // Check for C++ specific features
    if (/\bstd::|template\s*<|class\s+\w+\s*{/.test(trimmed)) {
      return "cpp";
    }
    return "c";
  }

  // CSS-specific
  if (/^(\.|#|@media|@import|@keyframes|:root)\s*.*\{/.test(trimmed)) {
    return "css";
  }

  // Shell-specific
  if (/^(if\s+\[\[?|case\s+.*\s+in|for\s+\w+\s+in)/.test(trimmed)) {
    return "sh";
  }

  // TypeScript-specific (interface, type keyword)
  if (/^(interface|type)\s+\w+\s*(=|{|\<)/.test(trimmed)) {
    return "ts";
  }

  // JavaScript/TypeScript (const/let/var with function or arrow)
  if (/^(const|let|var)\s+\w+/.test(trimmed)) {
    // Check for TypeScript type annotations (variable: type = value)
    if (/^(const|let|var)\s+\w+\s*:\s*\w+/.test(trimmed)) {
      return "ts";
    }
    if (/:\s*(string|number|boolean|any|void|Promise|Array|Map|Set)\b/.test(trimmed)) {
      return "ts";
    }
    return "js";
  }

  // Function declarations
  if (/^(async\s+)?function\s+\w+/.test(trimmed)) {
    return "js";
  }

  // Import/export (ES modules)
  if (/^(import|export)\s+/.test(trimmed)) {
    if (/:\s*(string|number|boolean|any)\b/.test(trimmed)) {
      return "ts";
    }
    return "js";
  }

  return "";
}

/**
 * Check if a position is inside a code block.
 *
 * @param {EditorState} state - The editor state
 * @param {number} pos - The position to check
 * @returns {boolean} - True if inside a code block
 */
export function isInsideCodeBlock(state, pos) {
  // Use the codeFenceField if available
  const fences = state.field(codeFenceField, false);

  if (fences && fences.length > 0) {
    const line = state.doc.lineAt(pos);
    const lineNum = line.number;

    for (const fence of fences) {
      if (lineNum >= fence.start && lineNum <= fence.end) {
        return true;
      }
      if (fence.start > lineNum) break;
    }
    return false;
  }

  // Fallback: scan nearby lines for code fences
  // This is less accurate but handles large documents where codeFenceField is empty
  const line = state.doc.lineAt(pos);
  const lineNum = line.number;
  const CODE_FENCE_REGEX = /^```(\w*)$/;

  // Scan backwards to find opening fence
  let inCodeBlock = false;
  const startLine = Math.max(1, lineNum - 100);

  for (let i = startLine; i <= lineNum; i++) {
    const lineText = state.doc.line(i).text;
    if (CODE_FENCE_REGEX.test(lineText)) {
      inCodeBlock = !inCodeBlock;
    }
  }

  return inCodeBlock;
}

/**
 * Show the code paste confirmation modal.
 * This is exported so it can be called from the paste handler.
 *
 * @param {Object} options
 * @param {string} options.suggestedLang - The detected language
 * @param {Function} options.onConfirm - Called with selected language when user confirms
 * @param {Function} options.onCancel - Called when user cancels (paste as plain text)
 */
export function showCodePasteModal(options) {
  initModals();
  openCodePaste(options);
}

/**
 * CodeMirror extension to detect code on paste and prompt user.
 * Only active for markdown files (not txt).
 */
export const pasteCodeDetection = EditorView.domEventHandlers({
  paste(event, view) {
    const text = event.clipboardData?.getData("text/plain");
    if (!text) return false;

    const pos = view.state.selection.main.head;

    // Skip if inside existing code block
    if (isInsideCodeBlock(view.state, pos)) {
      return false;
    }

    // Skip if doesn't look like code
    if (!looksLikeCode(text)) {
      return false;
    }

    // Detected code - prevent default paste and show modal
    event.preventDefault();
    const suggestedLang = detectLanguage(text);

    showCodePasteModal({
      suggestedLang,
      onConfirm: (selectedLang) => {
        const trimmedText = text.trim();
        // Check if cursor is at the beginning of a line
        const line = view.state.doc.lineAt(pos);
        const atLineStart = pos === line.from;
        // Add newline prefix if not at line start (``` must be at start of line)
        const prefix = atLineStart ? "" : "\n";
        // Add newline after closing ``` so the code block renders fully
        const wrapped = prefix + "```" + selectedLang + "\n" + trimmedText + "\n```\n";
        view.dispatch({
          changes: { from: pos, insert: wrapped },
          selection: { anchor: pos + wrapped.length },
        });
        view.focus();
      },
      onCancel: () => {
        // Paste as markdown (plain text)
        view.dispatch({
          changes: { from: pos, insert: text },
          selection: { anchor: pos + text.length },
        });
        view.focus();
      },
    });

    return true;
  },
});
