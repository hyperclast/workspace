// Shared mock data and setup helpers for Playwright e2e tests.
//
// React Native Web mappings used in selectors:
//   testID        → data-testid
//   accessibilityRole → role
//   accessibilityLabel → aria-label
//   TextInput     → <input> or <textarea>

const MOCK_TOKEN = "e2e-bearer-token";
const MOCK_CLIENT_ID = "e2e-client-id";

const MOCK_USER = {
  external_id: "user-1",
  username: "testuser",
  email: "test@example.com",
};

const MOCK_PROJECTS = [
  {
    external_id: "proj-1",
    name: "Project Alpha",
    description: "First test project",
    org: { external_id: "org-1", name: "Acme Corp" },
    pages: [
      {
        external_id: "page-1",
        title: "Getting Started",
        updated: "2026-03-22T10:00:00Z",
        created: "2026-03-20T10:00:00Z",
      },
      {
        external_id: "page-2",
        title: "Architecture Notes",
        updated: "2026-03-21T10:00:00Z",
        created: "2026-03-19T10:00:00Z",
      },
    ],
    files: [],
  },
  {
    external_id: "proj-2",
    name: "Project Beta",
    description: null,
    org: { external_id: "org-2", name: "Beta Inc" },
    pages: [],
    files: [],
  },
];

const MOCK_PAGE_1 = {
  external_id: "page-1",
  title: "Getting Started",
  updated: "2026-03-22T10:00:00Z",
  created: "2026-03-20T10:00:00Z",
  is_owner: true,
  details: {
    content:
      "# Getting Started\n\nWelcome to the project.\n\n## Setup\n\nFollow these steps to get started.",
  },
};

const MOCK_PAGE_2 = {
  external_id: "page-2",
  title: "Architecture Notes",
  updated: "2026-03-21T10:00:00Z",
  created: "2026-03-19T10:00:00Z",
  is_owner: false,
  details: {
    content:
      "# Architecture\n\nOverview of the system.\n\nSee also [Getting Started](/pages/page-1/).",
  },
};

const MOCK_STORAGE = { file_count: 3, total_bytes: 2097152 };

const MOCK_DEVICES = [
  {
    client_id: MOCK_CLIENT_ID,
    name: "Chrome Web",
    os: "web",
    is_current: true,
    last_active: "2026-03-22T12:00:00Z",
    created: "2026-03-01T00:00:00Z",
    app_version: "0.1.0",
  },
  {
    client_id: "device-other",
    name: "iPhone 15",
    os: "ios",
    is_current: false,
    last_active: "2026-03-20T08:00:00Z",
    created: "2026-03-05T00:00:00Z",
    app_version: "0.1.0",
  },
];

const MOCK_MENTIONS = {
  mentions: [
    {
      page_external_id: "page-1",
      page_title: "Team Updates",
      project_name: "Project Alpha",
      modified: "2026-03-22T12:00:00Z",
    },
  ],
};

/** Inject auth token into localStorage. Call BEFORE page.goto(). */
async function setupAuth(page) {
  await page.addInitScript(
    ({ token, clientId }) => {
      localStorage.setItem("access_token", token);
      localStorage.setItem("hyperclast_client_id", clientId);
    },
    { token: MOCK_TOKEN, clientId: MOCK_CLIENT_ID }
  );
}

/**
 * Intercept all backend API requests and respond with mock data.
 * Call BEFORE page.goto().
 *
 * @param {import("@playwright/test").Page} page
 * @param {object} [overrides]  Per-endpoint response overrides.
 */
async function mockApi(page, overrides = {}) {
  const pages = {
    "page-1": MOCK_PAGE_1,
    "page-2": MOCK_PAGE_2,
    ...(overrides.pages || {}),
  };

  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const method = route.request().method();
    const path = url.pathname;

    // ── Auth ──────────────────────────────────────────────

    if (method === "POST" && path.includes("/auth/login")) {
      if (overrides.loginError) {
        return route.fulfill({
          status: 400,
          contentType: "application/json",
          body: JSON.stringify(overrides.loginError),
        });
      }
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          status: 200,
          meta: { session_token: "session-tok" },
        }),
      });
    }

    if (method === "POST" && path.includes("/auth/signup")) {
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          status: 200,
          meta: { session_token: "session-tok" },
        }),
      });
    }

    // Device registration (POST) — returns access_token
    if (method === "POST" && path.match(/\/users\/me\/devices\/?$/)) {
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          access_token: MOCK_TOKEN,
          ...MOCK_DEVICES[0],
        }),
      });
    }

    // Device sync (PATCH)
    if (method === "PATCH" && path.match(/\/users\/me\/devices\//)) {
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(MOCK_DEVICES[0]),
      });
    }

    // Device revoke (DELETE)
    if (method === "DELETE" && path.match(/\/users\/me\/devices\//)) {
      return route.fulfill({ status: 204, body: "" });
    }

    // ── Resources ────────────────────────────────────────

    if (method === "GET" && path.match(/\/projects\/?$/)) {
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(overrides.projects || MOCK_PROJECTS),
      });
    }

    if (method === "GET" && path.match(/\/pages\/([\w-]+)\/?$/)) {
      const id = path.match(/\/pages\/([\w-]+)/)[1];
      const pg = pages[id];
      // Explicit null = 404 (for testing error states)
      if (pg === null || pg === undefined) {
        if (id in pages && pages[id] === null) {
          return route.fulfill({
            status: 404,
            contentType: "application/json",
            body: JSON.stringify({ detail: "Not found" }),
          });
        }
      }
      if (pg) {
        return route.fulfill({
          contentType: "application/json",
          body: JSON.stringify(pg),
        });
      }
      // Return a stub page for unknown IDs (e.g., newly created pages)
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          external_id: id,
          title: "Untitled",
          updated: new Date().toISOString(),
          created: new Date().toISOString(),
          is_owner: true,
          details: { content: "" },
        }),
      });
    }

    if (method === "POST" && path.match(/\/pages\/?$/)) {
      const body = route.request().postDataJSON();
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          external_id: "new-page-id",
          title: body?.title || "Untitled",
          updated: new Date().toISOString(),
          created: new Date().toISOString(),
          is_owner: true,
          details: { content: "" },
        }),
      });
    }

    if (method === "PUT" && path.match(/\/pages\/([\w-]+)\/?$/)) {
      const id = path.match(/\/pages\/([\w-]+)/)[1];
      const body = route.request().postDataJSON();
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          ...(pages[id] || MOCK_PAGE_1),
          ...body,
          external_id: id,
        }),
      });
    }

    if (method === "GET" && path.match(/\/mentions/)) {
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(overrides.mentions || MOCK_MENTIONS),
      });
    }

    if (method === "GET" && path.match(/\/users\/me\/?$/)) {
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(overrides.user || MOCK_USER),
      });
    }

    if (method === "GET" && path.match(/\/users\/storage/)) {
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(overrides.storage || MOCK_STORAGE),
      });
    }

    if (method === "GET" && path.match(/\/users\/me\/devices\/?$/)) {
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(overrides.devices || MOCK_DEVICES),
      });
    }

    // Unmatched API call — let it through
    return route.continue();
  });
}

/**
 * Convenience: set up auth + API mocks, then navigate.
 * Waits for the home screen to appear.
 */
async function navigateAuthenticated(page, path = "/", overrides = {}) {
  await setupAuth(page);
  await mockApi(page, overrides);
  await page.goto(path);
}

module.exports = {
  MOCK_TOKEN,
  MOCK_CLIENT_ID,
  MOCK_USER,
  MOCK_PROJECTS,
  MOCK_PAGE_1,
  MOCK_PAGE_2,
  MOCK_STORAGE,
  MOCK_DEVICES,
  MOCK_MENTIONS,
  setupAuth,
  mockApi,
  navigateAuthenticated,
};
