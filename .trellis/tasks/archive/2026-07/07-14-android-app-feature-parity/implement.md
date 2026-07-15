# Android app feature parity - implementation plan

## Preconditions

- Resolve all blocking questions in `prd.md` and receive explicit review approval.
- Run `task.py start` only after approval; then load `trellis-before-dev` before editing implementation code.
- Install or provide a supported JDK and Android SDK. The current machine has no discoverable Android SDK, Android Studio, `adb`, `sdkmanager`, or standalone Gradle.

## Ordered Checklist

1. Freeze the parity matrix
   - Map each R1-R12 workflow to the exact endpoint, permission, screen, and check.
   - Record approved platform-specific differences; do not silently drop any item.

2. Bootstrap the smallest Android project
   - Add one `android/app` Kotlin/Compose module, Gradle wrapper, pinned build versions, application ID, minimum/target API, and debug configuration.
   - Add only dependencies directly required for Compose/navigation, HTTP/SSE, and JSON.
   - Build and install an empty authenticated shell before adding feature code.

3. Prove the two risky integration seams first
   - Embed `https://shawnstronger.cloud`, reject cleartext traffic, then implement admin-only validated override/reset behavior and connectivity feedback.
   - Implement persistent cookies, serialized refresh/retry, session restore, and logout.
   - Integrate the PlayCaptcha challenge bridge and verify login/registration.
   - Verify authenticated WebView access and WebSockets for the proxied Hermes dashboard; if impossible, design and test the smallest backend handoff endpoint before proceeding.

4. Implement shared shell and permissions
   - Add session-aware navigation and adaptive phone/tablet chrome.
   - Derive destinations/actions from server permissions.
   - Add common loading, empty, error, confirmation, and external-link behavior.

5. Implement low-risk content vertical slices
   - Dashboard summary and quick actions.
   - Bookmarks plus folders, filter/search/favorite/move/order/delete behavior.
   - Excerpts plus featured shuffle.
   - Todos plus complete/reopen and clear-completed.
   - Add a focused test with each non-trivial slice.

6. Implement plans
   - Port pure date/period/progress functions first and cover boundary cases.
   - Add create/delete, date browsing, increment/decrement, metrics, seven-day chart, and per-plan statistics.

7. Implement netdisk search
   - Add query, normalized result states, source filters, and safe external intents.

8. Implement Hermes chat
   - Add conversation list/create/open/delete.
   - Add SSE parser and state machine, incremental rendering, stop, interruption markers, background recovery polling, and duplicate-prevention tests.

9. Implement administrator features
   - Add user/role/permission listing, role assignment, ban/unban, and account delete.
   - Add Hermes conversation audit/detail/delete.
   - Add Hermes status/refresh/start/stop and dashboard entry.

10. Full validation and polish
    - Complete TalkBack labels, keyboard/system-back behavior, responsive layouts, and destructive confirmations.
    - Run automated checks and the backend-connected manual parity matrix on minimum and target API devices.
    - Verify the existing browser client and backend regression suite.
    - Produce the Debug APK and record build/install instructions.

## Validation Commands

Run from `android/` after the wrapper exists:

```bash
./gradlew testDebugUnitTest
./gradlew lintDebug
./gradlew assembleDebug
./gradlew connectedDebugAndroidTest
```

Run from the repository root for shared regressions:

```bash
npm test
```

Manual checks must include:

- Fresh install, login/register/captcha, relaunch restore, token refresh, logout, banned user.
- Normal-user and admin permission matrices.
- Every R3-R11 workflow against a real Orbit backend.
- App background/foreground and process recreation during Hermes generation.
- External links and Hermes dashboard HTTP/WebSocket behavior.
- Installation and smoke test of the final artifact on the agreed oldest Android version.

## Risky Files and Rollback Points

- Authentication/cookie client: checkpoint after login, rotation, relaunch, and logout tests.
- Captcha bridge: checkpoint before content features.
- Any change under `backend/auth.py` or the auth routes: require security regression tests and a separate commit-sized rollback boundary.
- Hermes SSE client: checkpoint after stop and background recovery tests.
- Dashboard WebView cookie bridge or handoff endpoint: keep isolated so it can be reverted without affecting native status controls.
- Do not edit the existing web client unless a confirmed shared bug or compatibility change requires it.

## Review Gate Before `task.py start`

- [x] Native Kotlin/Jetpack Compose client selected; WebView limited to PlayCaptcha and Hermes Dashboard.
- [x] Server policy recorded: embedded current-server default, admin-only local override, session reset on change.
- [x] Exact default server recorded as `https://shawnstronger.cloud`.
- [x] Minimum Android version recorded as Android 8.0 / API 26.
- [x] First artifact recorded as an installable Debug APK; release signing and AAB are out of scope.
- [x] PRD convergence pass completed with no duplicate or resolved open questions.
- [x] User explicitly approved `prd.md`, `design.md`, and `implement.md` on 2026-07-14.
