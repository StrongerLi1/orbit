# Orbit Android manual parity checklist

Run this checklist against a disposable account on both API 26 and the current target API before a release build. The first delivery is a Debug APK, so unchecked items are explicit device/integration work rather than hidden automated coverage.

## Authentication and permissions

- [ ] Fresh install shows `https://shawnstronger.cloud`, completes PlayCaptcha, registers, and logs in.
- [ ] Login survives app recreation; an expired access cookie refreshes once; logout removes the session.
- [ ] Invalid credentials, banned account, offline server, and invalid custom origin show a readable error without tokens.
- [ ] A normal user sees content, netdisk, and Hermes chat only. An admin additionally sees access control and Hermes management.
- [ ] Only an authenticated admin can change/reset the server; switching logs out and the setting survives process recreation.

## Visual system and navigation

- [ ] Light and dark system themes switch without unreadable text, hard-coded white surfaces, or invisible controls.
- [ ] The bottom navigation exposes Home, Bookmarks, Plans, Todos, and More; secondary pages return to More with both the toolbar and system back actions.
- [ ] More shows Writings, Film Diary, Shared Library, Excerpts, Netdisk, Hermes, account details, and logout; permission-gated destinations remain filtered.
- [ ] Common narrow-phone layouts and 1.3x system font size keep primary actions reachable without horizontal clipping.
- [ ] Loading, partial-content error, empty, busy, disabled, destructive, banned, interrupted, and generating states use text or icons as well as color.

## Shared content

- [ ] Dashboard counts, featured excerpt, current plans, open todos, recent bookmarks, and quick destinations match the browser client.
- [ ] Bookmark create/search/filter/favorite/move/delete/external-open works; folder create/reorder/delete works and a non-empty folder is rejected.
- [ ] Excerpt create/list/shuffle/delete preserves author, source, date, and note.
- [ ] Daily/weekly/monthly plans create/delete, date navigation, increment/decrement, period progress, seven-day totals, and history statistics round-trip.
- [ ] Todo create with priority/due date, complete/reopen, delete, and clear-completed round-trip.
- [ ] Netdisk search shows source filters and opens a result in the system browser.

## Writings and film diary

- [ ] A user with `content:read` sees both More destinations; a read-only user can browse but sees no create, edit, status, or delete actions.
- [ ] Writings list own private/public posts plus other users' public posts. Private posts never appear to another user or admin.
- [ ] Create and edit all public/private × named/anonymous combinations; another viewer sees “匿名用户”, while the author retains management actions.
- [ ] Delete a writing only after confirmation; blank and over-8,000-character content cannot be submitted from the form.
- [ ] Create, edit, finish/reopen, and delete a film roll. A roll with exposures shows the cascade count before deletion.
- [ ] Create, edit, and delete exposures with every optional field. The suggested frame advances from the maximum but remains editable, and duplicate frames round-trip.
- [ ] Exposure UTC values display and edit as the device's local date/time, then survive a save/reload without shifting.
- [ ] “获取当前位置” prompts only from the exposure form. Precise and approximate grants fill an editable readable address when geocoding succeeds.
- [ ] Permission denial/permanent denial, disabled location services, timeout, and geocoder failure keep existing text, show a manual-entry hint, never expose coordinates, and never block saving.

## Shared library

- [ ] A user with `library:read` sees Shared Library in More; other users do not trigger a library request or see the destination.
- [ ] Catalog search and All/Unread/Read filters match the browser client, including loading, empty, no-result, retry, cover, and missing-cover states.
- [ ] A user with `library:upload` can select EPUB, PDF, MOBI, AZW3, or TXT from the system picker, optionally select a cover, review filename-derived title/author, manually correct either field, and confirm untouched fields prefer embedded metadata while manual values win.
- [ ] Unsupported uploads stay in the form with a readable error. A token refresh during multipart upload reopens both document streams and completes without loading the whole book into memory.
- [ ] A user with `library:manage` can edit title/author, replace or remove a cover, and delete a book only after the cascade warning; other users see none of those actions.
- [ ] Create a read with an optional named or anonymous review, then edit/delete only the current user's read. Reader totals and the grouped reader list refresh after every mutation.
- [ ] Create, toggle anonymity, and delete a review according to the server-projected ownership controls; another account cannot see owner-only actions.
- [ ] Download every supported format through Android's Save As picker. The chosen filename/MIME are sensible, cancellation is harmless, and no private duplicate remains in app storage.
- [ ] Create a public share link, copy it, and send it through the Android share sheet. An administrator can regenerate or revoke it only after confirmation, and an old/revoked URL stops downloading.
- [ ] Library-only 403, offline, cover, upload, download, and detail failures remain isolated from Home and the other content sections.

## Hermes and administration

- [ ] Conversation create/open/delete and incremental SSE responses work without duplicated messages.
- [ ] Stop preserves an interrupted assistant answer. Background/foreground, connection loss, and app recreation recover the server-side generation by polling.
- [ ] Admin can assign roles, ban/unban non-admins, delete a non-admin after confirmation, inspect audit messages, and delete an audited conversation after confirmation.
- [ ] Hermes status refresh/start/stop works. The authenticated dashboard WebView loads HTTP assets and WebSocket traffic; outside links leave the app.

## Packaging and regression

- [ ] Install `app/build/outputs/apk/debug/app-debug.apk` on API 26 and target API devices and complete a navigation smoke test.
- [ ] Reinstall the previous debug APK and confirm rollback requires no server migration or cleanup.
- [x] `testDebugUnitTest`, `lintDebug`, and `assembleDebug` pass with JDK 18 and Android SDK Platform 36 (27 JVM tests).
- [x] Repository-root `npm test` passes; no Android implementation change touched the existing browser/backend contract.
