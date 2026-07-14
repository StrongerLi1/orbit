# Orbit Android manual parity checklist

Run this checklist against a disposable account on both API 26 and the current target API before a release build. The first delivery is a Debug APK, so unchecked items are explicit device/integration work rather than hidden automated coverage.

## Authentication and permissions

- [ ] Fresh install shows `https://shawnstronger.cloud`, completes PlayCaptcha, registers, and logs in.
- [ ] Login survives app recreation; an expired access cookie refreshes once; logout removes the session.
- [ ] Invalid credentials, banned account, offline server, and invalid custom origin show a readable error without tokens.
- [ ] A normal user sees content, netdisk, and Hermes chat only. An admin additionally sees access control and Hermes management.
- [ ] Only an authenticated admin can change/reset the server; switching logs out and the setting survives process recreation.

## Shared content

- [ ] Dashboard counts, featured excerpt, current plans, open todos, recent bookmarks, and quick destinations match the browser client.
- [ ] Bookmark create/search/filter/favorite/move/delete/external-open works; folder create/reorder/delete works and a non-empty folder is rejected.
- [ ] Excerpt create/list/shuffle/delete preserves author, source, date, and note.
- [ ] Daily/weekly/monthly plans create/delete, date navigation, increment/decrement, period progress, seven-day totals, and history statistics round-trip.
- [ ] Todo create with priority/due date, complete/reopen, delete, and clear-completed round-trip.
- [ ] Netdisk search shows source filters and opens a result in the system browser.

## Hermes and administration

- [ ] Conversation create/open/delete and incremental SSE responses work without duplicated messages.
- [ ] Stop preserves an interrupted assistant answer. Background/foreground, connection loss, and app recreation recover the server-side generation by polling.
- [ ] Admin can assign roles, ban/unban non-admins, delete a non-admin after confirmation, inspect audit messages, and delete an audited conversation after confirmation.
- [ ] Hermes status refresh/start/stop works. The authenticated dashboard WebView loads HTTP assets and WebSocket traffic; outside links leave the app.

## Packaging and regression

- [ ] Install `app/build/outputs/apk/debug/app-debug.apk` on API 26 and target API devices and complete a navigation smoke test.
- [x] `testDebugUnitTest`, `lintDebug`, and `assembleDebug` pass with JDK 21 and Android SDK Platform 36 (15 JVM tests).
- [x] Repository-root `npm test` passes; no Android implementation change touched the existing browser/backend contract.
