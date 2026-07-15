# Android app feature parity - technical design

## Status

Planning-complete design for review. The approved client shape is a native Kotlin/Jetpack Compose application with a narrowly scoped WebView only for PlayCaptcha and Hermes Dashboard content.

## Design Principles

- Reuse the existing backend and its authorization rules.
- Build one Android application module; do not introduce domain/data abstractions with only one implementation.
- Use Android platform components and Kotlin coroutines/Flow before adding third-party libraries.
- Preserve security, validation, error handling, and accessibility even when choosing the minimal architecture.

## Proposed Project Boundary

```text
android/
  gradle wrapper and version catalog
  app/
    Compose UI and navigation
    Orbit API client and persistent cookie store
    application state holder plus screen-local Compose state
    models/serialization
    unit and instrumentation tests
```

The existing `backend/`, `public/`, and tests remain authoritative for server behavior. A backend change requires a concrete compatibility failure and a regression test.

## Client Architecture

- One `app` module using Kotlin and Jetpack Compose.
- A single application-scoped `OrbitClient` owns the configured base URL, HTTP client, JSON serialization, persistent cookies, refresh mutex, and API methods.
- One application-scoped `OrbitState` owns server-backed state and calls `OrbitClient`; short-lived form, filter, dialog, and selected-date state stays in each Compose screen.
- No repository interfaces, use-case classes, dependency-injection framework, local database, or offline synchronization until a second implementation or current requirement demands them.
- Navigation destinations: auth, dashboard, bookmarks, excerpts, plans, todos, netdisk, Hermes chat, admin settings, and Hermes service.

## Server and Session Contract

- `https://shawnstronger.cloud` is embedded in `BuildConfig` as the approved default server. Normal users never need to choose an address.
- After authenticating against the active server, an administrator may set or clear an app-private HTTPS origin override. Saving a change clears cookies/session state and requires authentication against the newly active server.
- A connection-error recovery action may reset only to the embedded approved default; it must not expose arbitrary server editing to normal users.
- The Android client calls the existing relative contracts under the active validated origin.
- The same-origin `orbit_access` and `orbit_refresh` values are stored in app-private persistent storage and sent only to the active Orbit origin. The current backend contract sets both cookies at `Path=/`; switching origin clears them.
- A 401 from a protected request enters one process-wide refresh mutex. The first caller invokes `/api/auth/refresh`; waiting callers retry once only after success. Refresh failure clears local session state and returns to login.
- Tokens and passwords must never be logged. The app rejects malformed base URLs and cleartext HTTP; only validated HTTPS origins are accepted.
- The current PlayCaptcha UI is web-native. In the native design, use a small controlled WebView/challenge bridge or a minimal backend-hosted challenge page, returning only the short-lived captcha token to the native auth form. Do not reimplement the challenge algorithm independently.

## Feature and Data Flow

### Shared content

Bookmarks, folders, excerpts, plans, and todos load from the existing collection endpoints. Mutations update the server first, then refresh the affected collection. Optimistic updates are limited to reversible UI interactions such as folder reordering and must roll back on failure.

Plan statistics remain client-derived to match the browser. The date key, active-range, daily/weekly/monthly period, history, and progress functions are ported as pure Kotlin and unit tested.

### Hermes chat

- Conversation CRUD uses the existing JSON endpoints.
- Message generation uses an HTTP POST whose response body is parsed as SSE events: `started`, `delta`, `completed`, and `error`.
- Screen state distinguishes idle, connecting, streaming, stopping, background-recovering, and failed.
- Explicit stop calls the independent stop endpoint before cancelling the local stream.
- Lifecycle/transport loss does not call stop. On resume, the client fetches the conversation; while `generating=true`, it polls at the existing two-second cadence and replaces temporary state when persistence completes.
- Only one user generation is allowed; UI prevents a second send and the backend remains the final arbiter.

### Web-native Hermes dashboard

The service status/start/stop UI is native. The dashboard itself opens in an in-app WebView pointed at the existing authenticated proxy path. The app synchronizes the same Orbit cookies into the WebView cookie manager, restricts navigation to the configured Orbit origin, delegates unrelated external URLs, and supports the dashboard WebSocket routes.

## UI and Android Adaptation

- Preserve workflows and information, not desktop layout. The first phone build uses a horizontally scrollable, permission-filtered destination row so all nine destinations remain available without a navigation dependency.
- Use native date/time pickers, confirmation dialogs, share-safe external intents, TalkBack labels, 48dp touch targets, system back, light/dark-safe contrast, and loading/empty/error states.
- Folder drag-and-drop may use Compose reorder gestures; accessible move-up/move-down actions provide equivalent ordering without drag.
- The global search keeps the current actual behavior: entering text navigates to bookmarks and filters bookmarks. It is not expanded to todos without a separately approved feature change.

## Compatibility and Migration

- No data migration is required; Android and web clients operate on the same backend records.
- The approved minimum is Android 8.0 / API 26. Compile/target SDK and plugin versions will be selected from the installed supported toolchain at implementation time and pinned by the wrapper/catalog.
- The first deliverable is a Debug APK. No release keystore, AAB, or store-publishing configuration is created in this task.
- Network Security Configuration rejects cleartext traffic; administrator overrides also require HTTPS.
- Upgrading from an older embedded origin clears its stored cookies before any request to the new HTTPS origin, so the user signs in once against the domain without replaying credentials across origins.

## Verification Strategy

- JVM unit tests: date/period statistics, URL validation, cookie persistence/matching, refresh serialization, permission-derived navigation, and SSE parsing/state transitions.
- HTTP integration tests with a local mock server: success/error payloads, 401-refresh-retry, concurrent refresh, cookie rotation, and SSE stop/recovery.
- Compose/instrumentation tests: auth navigation, role-gated destinations, forms, confirmations, date navigation, and representative CRUD.
- Manual backend-connected matrix: all PRD workflows on the agreed minimum API and current target API, app background/resume during Hermes generation, external links, dashboard WebSocket behavior, and process relaunch.
- Existing server regression command: `npm test`.

## Risks and Rollback

- Android build tools are absent locally. Implementation cannot satisfy the APK gate until a supported JDK and Android SDK are installed or made available.
- HttpOnly cookie synchronization into a dashboard WebView needs an instrumentation check on real WebView behavior. If it cannot be made reliable, add a narrowly scoped, short-lived dashboard handoff endpoint with backend tests rather than weakening cookie security.
- PlayCaptcha bridging is the other high-risk seam; validate it before implementing low-risk CRUD screens.
- Rollback is additive: remove/disable the `android/` deliverable and any explicitly marked mobile compatibility endpoint. Existing web/backend behavior remains intact.
