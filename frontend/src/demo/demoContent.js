/**
 * Demo content - curated pages showcasing Hyperclast features
 */

const WELCOME_CONTENT = `A fast, focused workspace for people who think in text. Try editing this page. Your changes stay local until you sign up.

## Try It Out
- [ ] Click this checkbox
- [ ] Type anywhere to edit
- [x] Already done!

Use **bold**, *italic*, \`inline code\`, and more. Blockquotes work too:

> This is a callout. Great for notes and asides.

Code blocks with syntax highlighting:

\`\`\`javascript
function greet(name) {
  return \`Hello, \${name}!\`;
}
\`\`\`

## Explore the Demo
Check out the other pages in the sidebar:
- [Internal Links](/pages/demo-links/) : Connect your ideas
- [Sections & Tasks](/pages/demo-sections/) : Organize with foldable sections

## Ready to Save Your Work?
Sign up to sync across devices and collaborate with your team.
`;

const LINKS_CONTENT = `Build a network of connected pages with internal links.

## Creating Links
1. Select the text you want to link
2. Press **Cmd/Ctrl+K** or click the link button in the toolbar
3. Search for a page to link to

Or type \`[Link Text](/pages/page-id/)\` directly.

## Try These Links
- [Welcome to Hyperclast](/pages/demo-welcome/)
- [Sections & Tasks](/pages/demo-sections/)

## Backlinks
Open the **Ref** tab in the right sidebar to see which pages link here, and where this page links to.

## Autocomplete
Type \`[\` and the editor suggests pages. Try typing \`[Welcome\` to see it in action.
`;

const SECTIONS_CONTENT = `Organize long documents with foldable sections. Click the arrow in the left gutter to fold any section.

## Today
- [x] Review yesterday's notes
- [ ] Check team messages
- [ ] Plan priorities
- [ ] Update project status

## Ideas
- Feature improvements
- Bug fixes to investigate
- Documentation updates

## Meeting Notes
**Attendees:** Alice, Bob, Charlie

**Discussion:**
1. Q1 planning review
2. Resource allocation
3. Timeline updates

**Action items:**
- [ ] Follow up on budget
- [ ] Schedule next sync

## Tips
- **Fold sections** to focus on what matters
- **Checkboxes** track progress inline
- **Headers** create collapsible sections
`;

const CSV_CONTENT = `Name,Email,Role,Status
Alice Johnson,alice@example.com,Engineer,Active
Bob Smith,bob@example.com,Designer,Active
Charlie Brown,charlie@example.com,Manager,On Leave
Diana Ross,diana@example.com,Engineer,Active
Eve Wilson,eve@example.com,Analyst,Active`;

const LOG_CONTENT = `192.168.1.1 - - [12/Jan/2026:10:15:32 +0000] "GET /api/users HTTP/2.0" 200 1234 "-" "Mozilla/5.0"
192.168.1.2 - - [12/Jan/2026:10:15:33 +0000] "POST /api/auth/login HTTP/2.0" 200 89 "-" "Mozilla/5.0"
10.0.0.5 - - [12/Jan/2026:10:15:34 +0000] "GET /static/app.js HTTP/2.0" 200 45678 "-" "Mozilla/5.0"
192.168.1.1 - - [12/Jan/2026:10:15:35 +0000] "GET /api/projects HTTP/2.0" 200 2341 "-" "Mozilla/5.0"
10.0.0.8 - - [12/Jan/2026:10:15:36 +0000] "GET /favicon.ico HTTP/2.0" 404 0 "-" "Mozilla/5.0"
192.168.1.3 - - [12/Jan/2026:10:15:37 +0000] "PUT /api/pages/abc123 HTTP/2.0" 200 567 "-" "Mozilla/5.0"`;

/**
 * Demo projects structure matching the API response format
 */
export const DEMO_PROJECTS = [
  {
    external_id: "demo-project",
    name: "Demo Workspace",
    description: "Try out Hyperclast features",
    org: {
      external_id: "demo-org",
      name: "Demo",
    },
    folders: [
      { external_id: "demo-folder-getting-started", parent_id: null, name: "Getting Started" },
      { external_id: "demo-folder-examples", parent_id: null, name: "Examples" },
    ],
    pages: [
      {
        external_id: "demo-welcome",
        title: "Welcome to Hyperclast",
        folder_id: "demo-folder-getting-started",
        created: new Date().toISOString(),
        modified: new Date().toISOString(),
      },
      {
        external_id: "demo-links",
        title: "Internal Links",
        folder_id: "demo-folder-getting-started",
        created: new Date().toISOString(),
        modified: new Date().toISOString(),
      },
      {
        external_id: "demo-sections",
        title: "Sections & Tasks",
        folder_id: "demo-folder-examples",
        created: new Date().toISOString(),
        modified: new Date().toISOString(),
      },
      {
        external_id: "demo-csv",
        title: "Sample Data",
        filetype: "csv",
        folder_id: "demo-folder-examples",
        created: new Date().toISOString(),
        modified: new Date().toISOString(),
      },
      {
        external_id: "demo-logs",
        title: "Access Logs",
        filetype: "log",
        created: new Date().toISOString(),
        modified: new Date().toISOString(),
      },
    ],
  },
];

/**
 * Demo page content by external_id
 */
export const DEMO_PAGES = {
  "demo-welcome": {
    external_id: "demo-welcome",
    title: "Welcome to Hyperclast",
    details: {
      content: WELCOME_CONTENT,
      filetype: "md",
    },
    filetype: "md",
    created: new Date().toISOString(),
    modified: new Date().toISOString(),
    updated: new Date().toISOString(),
    is_owner: true,
    project_id: "demo-project",
  },
  "demo-links": {
    external_id: "demo-links",
    title: "Internal Links",
    details: {
      content: LINKS_CONTENT,
      filetype: "md",
    },
    filetype: "md",
    created: new Date().toISOString(),
    modified: new Date().toISOString(),
    updated: new Date().toISOString(),
    is_owner: true,
    project_id: "demo-project",
  },
  "demo-sections": {
    external_id: "demo-sections",
    title: "Sections & Tasks",
    details: {
      content: SECTIONS_CONTENT,
      filetype: "md",
    },
    filetype: "md",
    created: new Date().toISOString(),
    modified: new Date().toISOString(),
    updated: new Date().toISOString(),
    is_owner: true,
    project_id: "demo-project",
  },
  "demo-csv": {
    external_id: "demo-csv",
    title: "Sample Data",
    details: {
      content: CSV_CONTENT,
      filetype: "csv",
    },
    filetype: "csv",
    created: new Date().toISOString(),
    modified: new Date().toISOString(),
    updated: new Date().toISOString(),
    is_owner: true,
    project_id: "demo-project",
  },
  "demo-logs": {
    external_id: "demo-logs",
    title: "Access Logs",
    details: {
      content: LOG_CONTENT,
      filetype: "log",
    },
    filetype: "log",
    created: new Date().toISOString(),
    modified: new Date().toISOString(),
    updated: new Date().toISOString(),
    is_owner: true,
    project_id: "demo-project",
  },
};

/**
 * Demo comments keyed by page external_id
 */
export const DEMO_COMMENTS = {
  "demo-welcome": [
    {
      external_id: "demo-cmt-1",
      parent_id: null,
      author: null,
      ai_persona: "socrates",
      requester: { external_id: "demo-user", email: "demo@example.com" },
      body: 'What does "fast" mean in this context? Fast loading times, fast editing, or fast navigation between pages?',
      anchor_from_b64: null,
      anchor_to_b64: null,
      anchor_text: "A fast, focused workspace for people who think in text.",
      created: new Date(Date.now() - 3600000).toISOString(),
      modified: new Date(Date.now() - 3600000).toISOString(),
      replies: [
        {
          external_id: "demo-cmt-1r",
          parent_id: "demo-cmt-1",
          author: { external_id: "demo-user", email: "demo@example.com", display_name: "You" },
          ai_persona: "",
          requester: null,
          body: "All of the above! But mainly fast editing. No lag even on long documents.",
          anchor_from_b64: null,
          anchor_to_b64: null,
          anchor_text: "",
          created: new Date(Date.now() - 3000000).toISOString(),
          modified: new Date(Date.now() - 3000000).toISOString(),
          replies: [],
        },
      ],
    },
    {
      external_id: "demo-cmt-2",
      parent_id: null,
      author: null,
      ai_persona: "einstein",
      requester: { external_id: "demo-user", email: "demo@example.com" },
      body: "The combination of checkboxes, code blocks, and blockquotes in a single editor is interesting: it positions this as a hybrid between a task manager and a writing tool.",
      anchor_from_b64: null,
      anchor_to_b64: null,
      anchor_text: "Use **bold**, *italic*, `inline code`, and more. Blockquotes work too:",
      created: new Date(Date.now() - 1800000).toISOString(),
      modified: new Date(Date.now() - 1800000).toISOString(),
      replies: [],
    },
    {
      external_id: "demo-cmt-3",
      parent_id: null,
      author: null,
      ai_persona: "dewey",
      requester: { external_id: "demo-user", email: "demo@example.com" },
      body: "For more on markdown-based editors and their design patterns, see [CommonMark Spec](https://spec.commonmark.org/) and [CodeMirror 6 documentation](https://codemirror.net/docs/).",
      anchor_from_b64: null,
      anchor_to_b64: null,
      anchor_text: "Code blocks with syntax highlighting:",
      created: new Date(Date.now() - 900000).toISOString(),
      modified: new Date(Date.now() - 900000).toISOString(),
      replies: [],
    },
    {
      external_id: "demo-cmt-3b",
      parent_id: null,
      author: null,
      ai_persona: "athena",
      requester: { external_id: "demo-user", email: "demo@example.com" },
      body: "You've outlined the features but haven't committed to a shipping order. **Pick the three highest-impact items and set a deadline for each.** Vague plans stay vague — decisive action moves you forward.",
      anchor_from_b64: null,
      anchor_to_b64: null,
      anchor_text: "",
      created: new Date(Date.now() - 600000).toISOString(),
      modified: new Date(Date.now() - 600000).toISOString(),
      replies: [],
    },
  ],
  "demo-sections": [
    {
      external_id: "demo-cmt-4",
      parent_id: null,
      author: { external_id: "demo-user", email: "demo@example.com", display_name: "Demo User" },
      ai_persona: "",
      requester: null,
      body: "We should break this into separate pages once the list gets longer.",
      anchor_from_b64: null,
      anchor_to_b64: null,
      anchor_text:
        "Organize long documents with foldable sections. Click the arrow in the left gutter to fold any section.",
      created: new Date(Date.now() - 7200000).toISOString(),
      modified: new Date(Date.now() - 7200000).toISOString(),
      replies: [],
    },
  ],
};

/**
 * Get a demo page by external_id
 */
export function getDemoPage(externalId) {
  return DEMO_PAGES[externalId] || null;
}

/**
 * Get the default demo page to show on first load
 */
export function getDefaultDemoPageId() {
  return "demo-welcome";
}
