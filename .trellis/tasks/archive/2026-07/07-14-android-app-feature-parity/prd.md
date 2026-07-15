# Android app feature parity

## Goal

Deliver an installable Android application for Orbit that preserves every current end-user and administrator workflow while continuing to use the existing FastAPI backend and shared MySQL data.

## Background and Confirmed Facts

- Orbit is currently a browser client (`public/index.html`, `public/app.js`) backed by FastAPI (`backend/main.py`) and MySQL/Redis (`README.md:1-92`).
- Authentication uses username/password, a PlayCaptcha challenge, short-lived access cookies, refresh-cookie rotation, automatic refresh, and logout (`public/app.js:44-142`, `backend/main.py:501-544`).
- The fixed roles are `admin` and `user`. Both can use shared content and Hermes chat; only admins can manage folders, agents, users, roles, and permissions (`backend/auth.py:24-45`).
- Bookmarks, todos, plans, folders, and excerpts are shared across authenticated users; Hermes conversations are isolated by user (`backend/database.py:11`, `backend/main.py:997-1114`).
- The current client exposes dashboard, bookmarks, netdisk search, excerpts, recurring plans, todos, Hermes chat, Hermes service management, and access-control screens (`public/index.html:36-199`).
- No Android project or mobile API variant exists in the repository. The local machine currently has Java 25 but no discoverable Android SDK, `adb`, `sdkmanager`, standalone Gradle, or Android Studio.
- Product decision: the deliverable is a native Kotlin/Jetpack Compose application. WebView use is limited to PlayCaptcha and the existing Hermes Dashboard, which are themselves web-native surfaces.
- Deployment evidence: on 2026-07-14 `https://shawnstronger.cloud/` serves Orbit, `/api/auth/me` returns the expected unauthenticated response, and a valid certificate covers the root and `www` names.
- Product decision: the Android build embeds `https://shawnstronger.cloud` as its default server origin. Normal users use it without configuration; an authenticated administrator may configure a local HTTPS override.
- Product decision: the minimum supported Android version is Android 8.0 / API 26.
- Product decision: the first delivery is an installable Debug APK; release signing, AAB packaging, and Google Play publication are deferred.

## Feature-Parity Requirements

### R1. Authentication and session lifecycle

- Provide login and public registration with the same username/password validation and PlayCaptcha gate.
- Persist the server-issued access and refresh cookies, retry one failed authenticated request after refresh, restore a valid session on launch, and support logout.
- Show server validation, banned-user, expired-session, connectivity, and invalid-server errors without exposing tokens.

### R2. Permission-aware navigation and authorization

- Render features from the permissions returned by `/api/auth/me`; do not infer access solely from a role label.
- Preserve backend enforcement for `content:read`, `content:write`, `netdisk:search`, `folders:manage`, `hermes:chat`, `agents:manage`, `users:manage`, and `roles:manage`.
- Preserve shared content semantics and per-user Hermes conversation isolation.

### R3. Dashboard

- Show greeting/date, bookmark count, incomplete todo count, today's plan completion count, up to four current plans, todos, and recent bookmarks.
- Show a random featured excerpt and allow navigation to its source screen.
- Provide quick entry points for bookmark, netdisk, excerpt, plan, and todo workflows.

### R4. Bookmarks and folders

- List, create, delete, favorite/unfavorite, open externally, filter by folder, search by title/URL/note/folder, and move bookmarks between folders.
- Sort favorites first and preserve the current title sort within the remaining items.
- Create folders for all content writers; let authorized folder managers reorder or delete folders, including the current confirmation and non-empty-folder rejection behavior.

### R5. Excerpts

- List, create, and delete excerpts with content, author, source, excerpt date, and optional note.
- Sort by excerpt date/creation time and support the current “shuffle featured excerpt” action.

### R6. Recurring plans and statistics

- Create and delete daily, weekly, and monthly plans with target count, active date range, time, duration, and color.
- Browse arbitrary dates, return to today, add or remove per-day completion counts, and preserve period-based progress semantics.
- Reproduce current day metrics, trailing-seven-day execution chart, per-plan success rate, cumulative count, and current-period progress.

### R7. Todos

- List and create todos with priority and optional due date; complete/reopen and delete individual todos.
- Separate active and completed todos and support deleting all completed todos.

### R8. Netdisk search

- Search PanSou through the existing Orbit API, show loading/empty/error states, display normalized result metadata, filter results by source, and open result links externally.

### R9. Hermes chat

- List, create, open, and soft-delete the signed-in user's conversations.
- Send messages through the existing POST/SSE endpoint, render incremental text, stop generation, display interrupted answers, and prevent conflicting sends.
- After an app background/connection interruption, poll the active conversation while the server continues generation and replace temporary state with the persisted result.

### R10. Administrator access control and audit

- List users, fixed roles, and permission descriptions; assign fixed roles, ban/unban non-admin users, and delete non-admin accounts with confirmation.
- List all Hermes conversations, inspect their messages and owner, and soft-delete a conversation with confirmation.

### R11. Hermes service administration

- Show installed/configured/running status and details; refresh status and issue start/stop commands.
- Open the authenticated proxied Hermes dashboard in an Android-compatible web surface because the dashboard itself is an existing web application.

### R12. Android delivery and compatibility

- Use one Android application module and the minimum architecture needed for the workflows above.
- Keep the existing browser client functional. Backend changes are allowed only when a documented mobile compatibility gap cannot be solved safely in the client.
- Provide a reproducible, installable Debug APK build, automated tests for critical client logic, and a manual parity checklist for device-only and integration behavior.
- Embed the approved default server origin. Show server override controls only to an authenticated administrator; changing or resetting the override clears the current session and reconnects through normal authentication.
- Set `minSdk` to API 26 and keep release signing/AAB configuration outside the first delivery.

## Acceptance Criteria

- [ ] AC1: A feature matrix maps R1-R12 to Android screens, API calls, and either an automated test or a documented manual check; no repository-confirmed workflow is absent.
- [ ] AC2: A clean checkout builds an installable debug APK with the checked-in Gradle wrapper and documented JDK/SDK prerequisites.
- [ ] AC3: Login, registration, captcha, cookie persistence, refresh rotation, relaunch restoration, banned-user handling, and logout pass against a running Orbit backend (R1).
- [ ] AC4: A normal user can use all shared content, netdisk, and Hermes chat workflows but cannot see or invoke admin-only actions; an admin can complete R10 and R11 (R2, R8-R11).
- [ ] AC5: CRUD and special actions for bookmarks/folders, excerpts, plans, and todos produce the same persisted results as the browser client (R3-R7).
- [ ] AC6: Plan period calculations and statistics are covered by deterministic unit tests for daily, weekly, monthly, date-boundary, zero-count, and removal cases (R6).
- [ ] AC7: Hermes streaming covers success, server error, explicit stop, process death/backgrounding, refresh expiry, and completed-result recovery without duplicate messages (R9).
- [ ] AC8: External bookmark/netdisk links and the authenticated Hermes dashboard open safely and return to the app without losing session state (R4, R8, R11).
- [ ] AC9: Android unit tests and lint pass; device/emulator smoke checks pass on the agreed minimum and target API levels; existing `npm test` passes after shared changes (R1-R12).
- [ ] AC10: The existing web application remains usable and no backend contract is silently broken (R12).

## Out of Scope

- Offline-first data mutation or conflict resolution; the current product requires its server.
- Push notifications, reminders, widgets, deep links, biometric login, or data export/import; these are not current browser features.
- A new multi-user ownership model for bookmarks, plans, todos, folders, or excerpts.
- Editing existing content fields where the current browser UI only supports delete or specialized patch actions.
- Release signing, AAB packaging, and Google Play publication.
