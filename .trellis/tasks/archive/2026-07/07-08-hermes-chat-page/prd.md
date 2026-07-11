# Hermes Chat Page

## Goal

Add an Orbit-native Hermes chat page so authorized normal users can chat with Hermes without receiving access to the full Hermes dashboard or agent management controls.

The page should feel like part of Orbit, call Hermes through the Orbit backend, preserve Hermes-native session context per Orbit conversation, and persist chat history in Orbit's database.

## Decisions And Evidence

- Orbit will build its own chat UI instead of embedding the Hermes dashboard.
- Access is role/permission controlled, and the default `user` role should receive chat access.
- The Orbit backend calls Hermes; browser clients do not call Hermes directly.
- Chat records are stored in Orbit's database and isolated per Orbit user for normal users.
- MVP uses non-streaming request/response chat. Streaming responses are a later enhancement.
- Each user can have multiple independent Hermes chat conversations.
- Only admins/agent managers can start or stop Hermes; chat users cannot control the Hermes service lifecycle.
- Each Orbit conversation maps to a real Hermes session. Orbit stores the `hermes_session_id` and resumes it on later messages so Hermes-native context and memory can continue.
- Admins can see and delete users' Hermes chat conversations in Orbit.
- Deleting a Hermes conversation is a soft delete in Orbit's database.
- MVP does not include a UI/API for viewing or restoring soft-deleted conversations.
- Current RBAC defines fixed permissions and roles in [backend/auth.py](/Users/king/Documents/code/a/backend/auth.py:24); the default `user` role currently receives `content:read`, `content:write`, and `netdisk:search`.
- RBAC defaults are re-seeded at startup and update permission/role rows from code in [backend/auth.py](/Users/king/Documents/code/a/backend/auth.py:421).
- Existing Hermes dashboard management and proxy endpoints are guarded by `agents:manage`, which should remain a higher-privilege admin/agent-management boundary in [backend/main.py](/Users/king/Documents/code/a/backend/main.py:455).
- Existing database initialization is schema-in-code and creates tables from [backend/database.py](/Users/king/Documents/code/a/backend/database.py:73).
- Existing sidebar navigation has a single `Hermes` admin nav item pointing at the dashboard management page in [public/index.html](/Users/king/Documents/code/a/public/index.html:46), so chat needs a separate user-facing entry.
- External evidence from the official `NousResearch/hermes-agent` repository (`v2026.7.7.2` on 2026-07-09): the dashboard chat tab is a PTY/WebSocket bridge to the Hermes TUI, not a clean non-streaming HTTP chat endpoint.
- External evidence from the official `NousResearch/hermes-agent` repository (`v2026.7.7.2` on 2026-07-09): `hermes -z/--oneshot` sends one prompt and prints only the final response text, while `hermes chat -Q -q` supports quiet single-query mode and emits a `session_id` on stderr.

## Requirements

- Add a new permission for Hermes chat access and include it in the default `user` role.
- Keep existing `agents:manage` behavior limited to Hermes service/dashboard management.
- Add an Orbit-native chat page visible only to users with the chat permission.
- Add backend chat APIs that require the chat permission and derive `user_id` from the authenticated Orbit session.
- Persist conversations and messages in MySQL with user ownership, timestamps, roles, and message content.
- Support multiple conversations per user with lightweight titles, using a separate conversation/message model rather than one global thread.
- Store the Hermes session id for each conversation after the first successful Hermes call, and use it for subsequent turns.
- Ensure normal users can only list, read, send to, and delete or clear their own Hermes chat data.
- Provide an admin-visible way to inspect Hermes chat conversations across users.
- Provide an admin-only way to delete other users' Hermes chat conversations, with a confirmation step in the UI.
- Conversation deletion should mark records as deleted and hide them from normal chat lists instead of physically removing messages.
- MVP should retain soft-deleted records only for future recovery/audit needs; normal app APIs should not expose deleted conversations.
- Backend should check/report Hermes availability and return useful errors when Hermes is not configured, not running, times out, or returns an invalid response.
- Chat users should see a clear unavailable state when Hermes is stopped or unreachable, without start/stop controls.
- Chat UI should support viewing previous conversations, starting a new conversation, sending a message, rendering assistant responses, loading/error states, and empty states.
- MVP chat submission should send one user message, wait for a complete Hermes response, then persist and render the complete assistant message.
- MVP should not simulate the Hermes dashboard PTY/WebSocket chat protocol.
- MVP should call Hermes through a quiet single-query CLI path that can return the final response and session id, rather than using the dashboard terminal websocket.
- The full Hermes dashboard and its websocket/terminal/event proxy must remain inaccessible to default users.

## Acceptance Criteria

- [ ] A default `user` can see and open the Hermes chat page after login.
- [ ] A default `user` cannot open the Hermes dashboard management page or `/hermes-dashboard/` unless they also have `agents:manage`.
- [ ] A default `user` cannot start or stop Hermes unless they also have `agents:manage`.
- [ ] A user with the chat permission can create an independent conversation, send a message, receive a Hermes response through Orbit, and see both messages persisted after refresh.
- [ ] A user can create and return to multiple separate Hermes conversations.
- [ ] Two different users cannot read or mutate each other's Hermes conversations or messages.
- [ ] Admins can view Hermes conversations across users.
- [ ] Admins can delete Hermes conversations across users after an explicit confirmation.
- [ ] Deleted conversations no longer appear in normal user chat lists, while their database records remain recoverable for future retention/audit needs.
- [ ] Users without the chat permission receive 403 for chat APIs and do not see the chat nav/page.
- [ ] Chat APIs return clear non-2xx errors for Hermes unavailable / timeout / malformed upstream response cases.
- [ ] Existing auth, RBAC, Hermes dashboard proxy, and shared content behavior continue to pass tests.
- [ ] New tests cover RBAC visibility/authorization, user isolation, database persistence, and Hermes upstream success/error handling.

## Out of Scope

- Exposing the full Hermes dashboard, terminal, model/key configuration, or agent management to default users.
- Multi-user shared chat rooms.
- Real-time collaboration between users.
- Streaming token output in the first release.
- Viewing or restoring soft-deleted conversations in the first release.
- Fine-grained model/key selection inside the Orbit chat UI unless required by the Hermes API integration.
