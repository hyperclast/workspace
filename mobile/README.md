# Hyperclast Mobile

Expo (React Native) mobile app for Hyperclast. Current scope: login/signup, project list, and tab navigation (proof of concept).

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

```bash
# Run all tests
npm test

# Run a specific test file
npx jest __tests__/stores/auth.test.js
npx jest __tests__/lib/api.test.js
```

Test infrastructure: Jest + jest-expo preset, `@testing-library/react-native`, manual mocks for `expo-secure-store`, `expo-crypto`, `expo-router`, `expo-device`.

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
        mentions.js             # Mentions placeholder
        settings.js             # Account info + logout
  stores/
    auth.js                     # Zustand auth store (token, hydrated, login/signup/logout)
  lib/
    api.js                      # API client (device registration, fetch, timeout)
    storage.js                  # Platform-aware secure storage + client ID generation
  __mocks__/                    # Jest manual mocks (expo-secure-store, expo-crypto, etc.)
  __tests__/
    stores/auth.test.js         # Auth store tests (11 tests)
    lib/api.test.js             # API client tests (11 tests)
  .env-template                 # Environment variable template
  app.json                      # Expo config
  package.json                  # Dependencies + Jest config
  jest.setup.js                 # Test setup (RNTL matchers)
```
