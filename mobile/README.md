# Hyperclast Mobile

Expo (React Native) mobile app for Hyperclast. Implements login/signup, project/page browsing, page editing, mentions, settings with device management, and tab navigation.

## Prerequisites

- Node.js 22 LTS (`nvm use`)
- Expo Go on your device for physical device testing (optional)
- Xcode (iOS Simulator) or Android Studio (Android Emulator) are optional

## Backend Prerequisites

The mobile app requires:

- `HEADLESS_CLIENTS` includes `"app"` in `backend/backend/settings/base.py` (already set by default)
- For Expo web dev: `http://localhost:8081` in `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` in `backend/backend/settings/dev.py` (already set)

## Setup

```bash
cd mobile
nvm use
npm install
cp .env-template .env
# Edit .env to set EXPO_PUBLIC_API_URL
```

For physical devices, use your machine's local IP instead of `localhost`:

```
EXPO_PUBLIC_API_URL=http://192.168.1.42:9800/api/v1
```

Ensure the backend binds `0.0.0.0` (Docker does this by default, or use `runserver_plus 0.0.0.0:9800`).

The host/netloc from `EXPO_PUBLIC_API_URL` (e.g. `192.168.1.42:9800`) must also be added to these backend env vars:

- `WS_ALLOWED_HOSTS` — so Django accepts requests from that host (e.g., `192.168.1.42`)
- `WS_CSRF_TRUSTED_ORIGINS` — as a full origin, e.g. `http://192.168.1.42:9800`

## Running

```bash
# Start Expo dev server
npm start

# Or run directly on a platform
npm run ios        # iOS Simulator
npm run android    # Android Emulator
npm run web        # Web browser (dev only)
```

## Auth Flow

The app uses per-device bearer token auth:

1. Login/signup via `/api/app/v1/auth/login` with `X-Client-Type: app`
2. allauth returns `meta.session_token` in JSON (no cookies)
3. Register device via `POST /api/v1/users/me/devices/` with session token + device metadata
4. Server returns a per-device `access_token` (independently revocable)
5. Token stored in expo-secure-store (iOS Keychain / Android Keystore, localStorage on web for dev)
6. All API calls use `Authorization: Bearer <token>`
7. Logout calls `DELETE /api/v1/users/me/devices/{client_id}/` to revoke server-side

See [docs/api/internal/auth.md](../docs/api/internal/auth.md) for endpoint details.

## Testing

### Unit Tests

```bash
# Run all unit tests
npm test

# Run a specific test file or directory
npx jest __tests__/stores/auth.test.js
npx jest __tests__/screens/
npx jest __tests__/lib/
```

131 tests across 12 test suites. Test infrastructure: Jest + jest-expo preset, `@testing-library/react-native`, manual mocks for `expo-secure-store`, `expo-crypto`, `expo-router`, `expo-device`.

### E2E Tests (Playwright)

E2E tests run against the Expo web build using Playwright (Chromium). All backend API calls are intercepted and mocked (see `e2e/helpers.js`), so no running backend is required.

**First-time setup:**

```bash
# Install Playwright browsers (chromium only)
npx playwright install chromium
```

**Running E2E tests:**

```bash
# Run all E2E tests (headless)
npm run test:e2e

# Run in headed mode (opens browser window)
npm run test:e2e:headed

# Run a specific spec file
npx playwright test e2e/auth.spec.js

# View the HTML test report after a run
npx playwright show-report
```

Playwright auto-starts the Expo web dev server on port 8081 by default. To use a different port, set `EXPO_WEB_PORT`:

```bash
EXPO_WEB_PORT=8099 npm run test:e2e
```

If you already have Expo running on the target port, Playwright will reuse the existing server.

6 spec files covering auth, navigation, projects, pages, mentions, and settings.

## Project Structure

```
mobile/
  app/
    _layout.js                  # Root layout (Stack with route groups)
    (auth)/
      _layout.js                # Auth guard (redirects if already logged in)
      login.js                  # Login / signup screen (combined)
    (app)/
      _layout.js                # App guard (redirects to login if no token)
      (tabs)/
        _layout.js              # Tab bar (Home, Mentions, Settings)
        index.js                # Home: project list with pull-to-refresh
        mentions.js             # Mentions: pages where user is @mentioned
        settings.js             # Account, storage, devices, app version, logout
      project/
        [projectId].js          # Project detail: page list + FAB for new page
      page/
        [pageId]/
          _layout.js            # Page route stack layout
          index.js              # Page view: markdown rendering + internal links
          edit.js               # Page edit: title + content TextInput + save
  stores/
    auth.js                     # Zustand auth store (token, hydrated, login/signup/logout)
    projects.js                 # Zustand project store (projects list, fetch)
    pages.js                    # Zustand page store (current page, fetch/update/create)
  lib/
    api.js                      # API client (device registration, CRUD, timeout)
    storage.js                  # Platform-aware secure storage + client ID generation
  __mocks__/                    # Jest manual mocks (expo-secure-store, expo-crypto, etc.)
  __tests__/
    stores/                     # Store tests (auth, projects, pages)
    screens/                    # Screen tests (home, projectDetail, pageView, pageEdit, mentions, settings)
    lib/                        # API client tests
  .env-template                 # Environment variable template
  app.json                      # Expo config
  package.json                  # Dependencies + Jest config
  jest.setup.js                 # Test setup (RNTL matchers)
```
