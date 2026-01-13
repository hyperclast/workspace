/**
 * Demo content - curated pages showcasing Hyperclast features
 */

const WELCOME_CONTENT = `A fast, focused workspace for people who think in text. Try editing this page—your changes stay local until you sign up.

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
- [Internal Links](/pages/demo-links/) — connect your ideas
- [Sections & Tasks](/pages/demo-sections/) — organize with foldable sections

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
Open the **Ref** tab in the right sidebar to see which pages link here—and where this page links to.

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
    pages: [
      {
        external_id: "demo-welcome",
        title: "Welcome to Hyperclast",
        created: new Date().toISOString(),
        modified: new Date().toISOString(),
      },
      {
        external_id: "demo-links",
        title: "Internal Links",
        created: new Date().toISOString(),
        modified: new Date().toISOString(),
      },
      {
        external_id: "demo-sections",
        title: "Sections & Tasks",
        created: new Date().toISOString(),
        modified: new Date().toISOString(),
      },
      {
        external_id: "demo-csv",
        title: "Sample Data",
        filetype: "csv",
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
