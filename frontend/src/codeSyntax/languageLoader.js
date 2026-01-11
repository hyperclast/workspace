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
