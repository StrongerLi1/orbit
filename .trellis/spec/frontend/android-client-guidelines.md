# Android Client Guidelines

## Scenario: Native Orbit client over the existing web API

### 1. Scope / Trigger

Use this contract for code under `android/`. The Android app is another client of the existing FastAPI API and shared data; it must not fork server semantics. Compose is native except for PlayCaptcha and the proxied Hermes Dashboard, which remain controlled WebViews.

### 2. Signatures

```kotlin
class OrbitClient(context: Context) {
    suspend fun restoreUser(): OrbitUser
    suspend fun bookmarks(): List<Bookmark>
    suspend fun todos(): List<Todo>
    suspend fun plans(): List<Plan>
    suspend fun folders(): List<Folder>
    suspend fun excerpts(): List<Excerpt>
    suspend fun streamHermes(id: String, content: String, onEvent: suspend (SseEvent) -> Unit)
    suspend fun stopHermes(id: String)
    fun setServerOverride(value: String?)
}

data class HermesStreamProjection(val conversationId: String, val content: String = "")
```

Authoritative routes remain `/api/auth/**`, `/api/{bookmarks,todos,plans,folders,excerpts}`, `/api/netdisk/search`, `/api/hermes-chat/**`, `/api/admin/**`, `/api/agents/hermes/**`, and `/hermes-dashboard/**`.

### 3. Contracts

- Default origin: `https://shawnstronger.cloud`; all cleartext traffic is rejected. A custom override must be an HTTPS origin with no path, query, or fragment.
- Persist the origin that owns stored cookies. When the embedded default or an override changes, clear old cookies before the first request so credentials are never replayed to another origin.
- Only an authenticated administrator can change/reset the override. Changing it clears cookies and the current session.
- Persist server `orbit_access` and `orbit_refresh` cookies privately. A protected-request 401 enters one refresh lock, calls `/api/auth/refresh`, and retries once. Refresh failure clears cookies and returns UI state to login.
- Permissions returned by `/api/auth/me` gate destinations and actions; role labels are not permission substitutes.
- Load bookmarks, todos, plans, folders, and excerpts independently. A non-auth failure in one collection must retain successful collections, keep the restored user signed in, identify the failed collection, and expose retry. Only a terminal 401 resets the session.
- SSE decoding has one typed boundary: `started`, `delta`, `completed`, `error`. Delta order is preserved. `HermesStreamProjection.conversationId` owns temporary text.
- Viewing B while A generates is allowed. A callbacks may update A/list state but must not write temporary text into B or force active navigation back to A.
- Explicit Stop targets the generating conversation and calls the Stop API before disconnecting locally. Passive lifecycle/transport loss never calls Stop; poll detail every two seconds, retry transient poll failures after three seconds, and install durable messages when `generating=false`.
- PlayCaptcha WebView returns only a verified callback; native code then requests the short-lived token. Hermes Dashboard cookies are copied to `CookieManager`, navigation is restricted to the active Orbit origin, and external links use the system browser.

### 4. Validation & Error Matrix

| Condition | Required behavior |
| --- | --- |
| Custom HTTP origin or origin with path | Reject locally |
| Protected request returns 401 | Serialized refresh, then one retry |
| Refresh returns 401 | Clear cookies/session and show login |
| One content collection returns non-401 error | Keep other collection results, show the failed label, allow retry |
| Content load fails after `/auth/me` succeeds | Keep the restored user; do not misclassify as login failure |
| SSE chunk contains multiple events | Parse every event in original order |
| User views B while A streams | B shows no A temporary text; stream continues |
| Passive disconnect or Activity recreation | Disconnect reader only; server continues; reload/poll |
| User presses Stop while viewing B | Stop A, the owned generating conversation |
| Poll returns 401/403/404 | Stop recovery and surface terminal auth/access/not-found state |
| Poll has transient network/5xx error | Retry without enabling a second send |
| WebView requests another origin | Delegate externally; do not navigate in-app |

### 5. Good/Base/Bad Cases

- Good: access expires during a content mutation, one caller rotates refresh cookies, and all callers retry with the new cookie revision.
- Base: A generates, the user reads B, then returns to A and sees A's current text or durable result.
- Bad: store only a global `streamedText`; switching to B renders A's deltas in B and completion forces navigation back to A.

### 6. Tests Required

- JVM: daily/weekly/monthly plan boundaries and history; SSE chunks split/coalesced; typed event decoding; `HermesStreamProjection.textFor` isolation; permission projection; origin validation; normalized netdisk decoding.
- JVM: one failed content section does not prevent later sections from running; a 401 remains terminal.
- Android lint and package: `testDebugUnitTest`, `lintDebug`, `assembleDebug`.
- Device/backend: PlayCaptcha login/register, cookie relaunch/refresh/logout, permission matrix, all CRUD workflows, SSE Stop/passive recovery/process recreation, external intents, and Dashboard HTTP/WebSocket traffic on API 26 and target API.
- Shared regression: repository-root `npm test`.

### 7. Wrong vs Correct

```kotlin
// Wrong: temporary text has no owner and completion hijacks navigation.
streamedText += delta
activeConversation = client.conversation(originId)

// Correct: project by origin and publish durable state only if still active.
streamProjection = streamProjection?.append(delta)
val persisted = client.conversation(originId)
if (activeConversation?.id == originId) activeConversation = persisted
```
