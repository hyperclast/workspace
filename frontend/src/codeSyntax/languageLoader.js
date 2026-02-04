// Display names for language codes
export const languageDisplayNames = {
  py: "Python",
  python: "Python",
  js: "JavaScript",
  javascript: "JavaScript",
  jsx: "JSX",
  ts: "TypeScript",
  typescript: "TypeScript",
  tsx: "TSX",
  html: "HTML",
  css: "CSS",
  json: "JSON",
  md: "Markdown",
  markdown: "Markdown",
  sql: "SQL",
  rust: "Rust",
  rs: "Rust",
  go: "Go",
  golang: "Go",
  java: "Java",
  c: "C",
  cpp: "C++",
  "c++": "C++",
  php: "PHP",
  xml: "XML",
  ruby: "Ruby",
  rb: "Ruby",
  sh: "Shell",
  bash: "Bash",
};

// Canonical language options for the dropdown (alphabetical, Plain Text first)
export const languageOptions = [
  { code: "", name: "Plain Text" },
  { code: "c", name: "C" },
  { code: "cpp", name: "C++" },
  { code: "css", name: "CSS" },
  { code: "go", name: "Go" },
  { code: "html", name: "HTML" },
  { code: "java", name: "Java" },
  { code: "js", name: "JavaScript" },
  { code: "json", name: "JSON" },
  { code: "jsx", name: "JSX" },
  { code: "md", name: "Markdown" },
  { code: "php", name: "PHP" },
  { code: "py", name: "Python" },
  { code: "ruby", name: "Ruby" },
  { code: "rust", name: "Rust" },
  { code: "sh", name: "Shell" },
  { code: "sql", name: "SQL" },
  { code: "ts", name: "TypeScript" },
  { code: "tsx", name: "TSX" },
  { code: "xml", name: "XML" },
];

// Helper to wrap legacy mode in LanguageSupport-like structure
async function wrapLegacyMode(modeImport) {
  const { StreamLanguage } = await import("@codemirror/language");
  const mode = await modeImport;
  return { language: StreamLanguage.define(mode[Object.keys(mode)[0]]) };
}

const languageMap = {
  // Python
  py: () => import("@codemirror/lang-python").then((m) => m.python()),
  python: () => import("@codemirror/lang-python").then((m) => m.python()),
  // JavaScript
  js: () => import("@codemirror/lang-javascript").then((m) => m.javascript()),
  javascript: () => import("@codemirror/lang-javascript").then((m) => m.javascript()),
  jsx: () => import("@codemirror/lang-javascript").then((m) => m.javascript({ jsx: true })),
  // TypeScript
  ts: () => import("@codemirror/lang-javascript").then((m) => m.javascript({ typescript: true })),
  typescript: () =>
    import("@codemirror/lang-javascript").then((m) => m.javascript({ typescript: true })),
  tsx: () =>
    import("@codemirror/lang-javascript").then((m) =>
      m.javascript({ typescript: true, jsx: true })
    ),
  // HTML
  html: () => import("@codemirror/lang-html").then((m) => m.html()),
  // CSS
  css: () => import("@codemirror/lang-css").then((m) => m.css()),
  // JSON
  json: () => import("@codemirror/lang-json").then((m) => m.json()),
  // Markdown
  md: () => import("@codemirror/lang-markdown").then((m) => m.markdown()),
  markdown: () => import("@codemirror/lang-markdown").then((m) => m.markdown()),
  // SQL
  sql: () => import("@codemirror/lang-sql").then((m) => m.sql()),
  // Rust
  rust: () => import("@codemirror/lang-rust").then((m) => m.rust()),
  rs: () => import("@codemirror/lang-rust").then((m) => m.rust()),
  // Go
  go: () => import("@codemirror/lang-go").then((m) => m.go()),
  golang: () => import("@codemirror/lang-go").then((m) => m.go()),
  // Java
  java: () => import("@codemirror/lang-java").then((m) => m.java()),
  // C/C++
  c: () => import("@codemirror/lang-cpp").then((m) => m.cpp()),
  cpp: () => import("@codemirror/lang-cpp").then((m) => m.cpp()),
  "c++": () => import("@codemirror/lang-cpp").then((m) => m.cpp()),
  // PHP
  php: () => import("@codemirror/lang-php").then((m) => m.php()),
  // XML
  xml: () => import("@codemirror/lang-xml").then((m) => m.xml()),
  // Ruby (legacy mode)
  ruby: () => wrapLegacyMode(import("@codemirror/legacy-modes/mode/ruby")),
  rb: () => wrapLegacyMode(import("@codemirror/legacy-modes/mode/ruby")),
  // Shell (legacy mode)
  sh: () => wrapLegacyMode(import("@codemirror/legacy-modes/mode/shell")),
  bash: () => wrapLegacyMode(import("@codemirror/legacy-modes/mode/shell")),
};

const cache = new Map();

export async function getLanguage(lang) {
  if (!lang || !languageMap[lang.toLowerCase()]) return null;
  const key = lang.toLowerCase();
  if (!cache.has(key)) {
    cache.set(key, await languageMap[key]());
  }
  return cache.get(key);
}

export function isLanguageSupported(lang) {
  return lang && languageMap[lang.toLowerCase()] !== undefined;
}
