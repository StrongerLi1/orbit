# Hermes Chat Page Design

## Summary

Add an Orbit-native Hermes chat surface for normal users. Orbit owns the browser UI, RBAC, user isolation, database persistence, and admin visibility/deletion. Hermes owns the agent runtime and native session context.

The MVP uses non-streaming calls. Each Orbit conversation maps to one Hermes session id, stored after the first successful turn and resumed for later turns.

## Boundaries

- Orbit owns:
  - authentication and authorization
  - conversation/message storage in MySQL
  - user-facing and admin-facing chat UI
  - soft deletion and normal/admin query scoping
  - invoking Hermes through a local CLI command
- Hermes owns:
  - provider/model/API-key configuration
  - agent execution
  - native session context, memory, tools, and resume behavior
- Existing Hermes dashboard management stays behind `agents:manage`.
- The new chat permission grants chat usage, not process lifecycle control.

## Authorization

Add a permission such as `hermes:chat`.

- `admin` receives it automatically because admin maps to all permissions.
- `user` receives it explicitly by default.
- Chat APIs require `hermes:chat`.
- Admin cross-user inspection/deletion should require an admin-level permission already limited to admins. Prefer `users:manage` for the MVP if no new admin chat permission is created; document the choice in code/tests.
- `agents:manage` remains required for status/start/stop and `/hermes-dashboard/*`.

Frontend guards:

- Show the user chat nav/page when `hasPermission("hermes:chat")`.
- Show existing Hermes management nav/page only when `hasPermission("agents:manage")`.
- Normal users can operate only their own conversations.
- Admin UI can view/delete conversations across users.

## Database

Add two MySQL tables during `initialize_database()`:

`hermes_conversations`

- `id VARCHAR(64) PRIMARY KEY`
- `user_id VARCHAR(64) NOT NULL`
- `title VARCHAR(160) NOT NULL`
- `hermes_session_id VARCHAR(120) NOT NULL DEFAULT ''`
- `created_at VARCHAR(40) NOT NULL`
- `updated_at VARCHAR(40) NOT NULL`
- `deleted_at VARCHAR(40) NOT NULL DEFAULT ''`
- indexes on `(user_id, deleted_at, updated_at)` and `(deleted_at, updated_at)`

`hermes_messages`

- `id VARCHAR(64) PRIMARY KEY`
- `conversation_id VARCHAR(64) NOT NULL`
- `user_id VARCHAR(64) NOT NULL`
- `role VARCHAR(20) NOT NULL`
- `content MEDIUMTEXT NOT NULL`
- `created_at VARCHAR(40) NOT NULL`
- index on `(conversation_id, created_at)`

Soft deletion sets `hermes_conversations.deleted_at`; message rows remain. Normal APIs exclude deleted conversations. MVP does not expose restore or deleted-list APIs.

## Backend API

Use explicit Hermes chat endpoints instead of the generic `/api/{collection}` CRUD path, because authorization and user ownership are different.

Proposed contracts:

`GET /api/hermes-chat/conversations`

Returns the current user's non-deleted conversations with last message metadata if easy to compute.

`POST /api/hermes-chat/conversations`

Creates a conversation, optionally with a title. Empty title is allowed and can be replaced from the first message.

`GET /api/hermes-chat/conversations/{id}`

Returns one owned non-deleted conversation and its messages.

`POST /api/hermes-chat/conversations/{id}/messages`

Body:

```json
{ "content": "hello" }
```

Behavior:

1. Validate content is non-empty and capped.
2. Load an owned, non-deleted conversation.
3. Build Hermes command:
   - first turn: quiet single-query command without `--resume`
   - later turns: quiet single-query command with `--resume <hermes_session_id>`
4. Run command without a shell, with configured timeout and environment.
5. Parse stdout as assistant content.
6. Parse stderr for `session_id: <id>` and save it if present.
7. Persist user and assistant messages after Hermes succeeds.
8. Update conversation title from the first user message if title is empty/default.

`DELETE /api/hermes-chat/conversations/{id}`

Soft-deletes an owned conversation.

Admin endpoints can live under `/api/admin/hermes-chat/conversations`, requiring admin permission:

- list non-deleted conversations across users, including username
- get one conversation and its messages
- soft-delete any conversation

## Hermes Invocation

The official Hermes dashboard chat tab is a PTY/WebSocket bridge to the TUI, so Orbit should not emulate it.

Use `hermes chat -Q -q <prompt>` for the MVP because it emits final response on stdout and `session_id: ...` on stderr. Use `--resume <session>` on later turns. Keep the command configurable so production can include `env HOME=/opt/orbit HERMES_HOME=/opt/orbit/.hermes /usr/local/bin/hermes ...`.

Recommended settings:

- `HERMES_CHAT_COMMAND`, default `hermes chat -Q -q`
- `HERMES_CHAT_TIMEOUT`, default longer than dashboard probe, e.g. `120`

Command construction should split the configured base command with `shlex.split`, append `--resume <id>` only when needed, and append the prompt as a final argument. Do not invoke through a shell.

Errors:

- `503` when Hermes CLI command is unavailable or not configured
- `503` when dashboard/status indicates Hermes is not running, if chat depends on the running Hermes install
- `504` on timeout
- `502` when Hermes exits non-zero or produces no assistant output

## Frontend Flow

Add a separate chat page, e.g. `#hermes-chat`, visible to default users.

Layout:

- conversation list with new-chat action
- message transcript panel
- text input and send button
- loading state while waiting for Hermes
- empty state for no conversations and no messages
- unavailable/error state for Hermes failures

Admin:

- Add admin-visible chat inspection in the existing admin area or as a separate admin subsection.
- Show username, title, updated time, and delete action with confirmation.
- Admin reads/deletes through admin endpoints, not normal user endpoints.

## Data Flow

User sends prompt:

`UI form -> POST /api/hermes-chat/conversations/{id}/messages -> permission/user ownership check -> Hermes subprocess -> parse output/session id -> insert messages/update conversation -> API response -> frontend render`

Admin deletes:

`Admin UI -> DELETE /api/admin/hermes-chat/conversations/{id} -> admin permission check -> set deleted_at -> lists hide it`

## Compatibility

- Existing dashboard management page and `/hermes-dashboard/*` proxy stay unchanged and remain admin-only.
- Existing shared content APIs remain unchanged.
- RBAC seeding updates existing `user` role permissions at startup; current sessions may need refresh/re-login to receive new permissions in JWT cookies.

## Rollback

Revert the new permission, chat tables, repository helpers, endpoints, frontend nav/page/admin UI, settings, tests, and docs. Soft-deleted records remain in MySQL if the table is not dropped; dropping tables should be a manual DBA decision, not automatic rollback.
