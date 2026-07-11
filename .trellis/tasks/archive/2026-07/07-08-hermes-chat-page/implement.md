# Hermes Chat Page Implementation Plan

## Steps

- [x] Add backend settings for Hermes chat command and timeout.
- [x] Add `hermes:chat` permission and include it in the default `user` role.
- [x] Add `hermes_conversations` and `hermes_messages` tables in database initialization.
- [x] Add backend repository/helper functions for:
  - user conversation list/read/create
  - message insert/list
  - user/admin soft delete
  - admin conversation list/read across users
- [x] Add Hermes chat invocation helper:
  - command split/availability
  - prompt validation/capping
  - optional `--resume`
  - timeout/non-zero/no-output handling
  - `session_id` parsing from stderr
- [x] Add user chat API endpoints under `/api/hermes-chat/*`.
- [x] Add admin chat API endpoints under `/api/admin/hermes-chat/*`.
- [x] Add frontend state, nav guard, chat page markup, rendering, actions, and send flow.
- [x] Add admin UI for cross-user conversation inspection and soft delete with confirmation.
- [x] Update README / docs with the chat page, permission model, command config, and non-streaming MVP note.
- [x] Add tests for RBAC defaults, user isolation, soft deletion, admin visibility/deletion, and Hermes success/error handling.

## Validation Commands

Run as much of this as local services allow:

```bash
python3 -m compileall backend
npm test
pytest
```

Focused checks:

```bash
pytest tests/test_hermes_agent.py
pytest tests/test_rbac.py
```

Manual verification when MySQL/Redis/Hermes are available:

```bash
command -v hermes
hermes dashboard --status || true
hermes chat -Q -q "Say hello" 2>/tmp/hermes-chat.err
cat /tmp/hermes-chat.err
```

Browser checks:

- default user sees `#hermes-chat`
- default user does not see/open `#hermes` management
- sending a message persists after refresh
- second user cannot open the first user's conversation
- admin can list/read/delete user conversations

## Risk Points

- `hermes chat -Q -q` may require a configured provider and can take a long time; use a dedicated timeout and clear errors.
- Parsing `session_id` from stderr is an external CLI contract. Tests should cover missing session id and non-zero exit.
- Current auth cookies include permissions; existing logged-in users may need token refresh/re-login after RBAC changes.
- Soft delete must be applied consistently to normal and admin list/read endpoints.
- Frontend `public/app.js` is a single large file; keep changes localized and reuse existing `request`, `toast`, `showPage`, and render patterns.

## Rollback Points

- RBAC change is small but affects default user permissions.
- Database table creation is additive.
- API endpoints are new and can be removed without touching existing CRUD.
- Frontend nav/page additions are independent of existing dashboard management page.
