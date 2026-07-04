# Admin account deletion and ban controls design

## Architecture

This feature extends the existing RBAC admin surface instead of creating a new management area. The backend remains the source of truth for account safety rules, and the frontend only hides or disables controls as a convenience.

## Data Model

- Add a simple ban status column to `users`, for example `is_banned TINYINT(1) NOT NULL DEFAULT 0`.
- Existing deployments need startup-time schema compatibility because tables are created by `initialize_database()` rather than a migration framework. Add an idempotent `ALTER TABLE users ADD COLUMN ...` path after `CREATE TABLE IF NOT EXISTS users`.
- Do not add ban reason, expiration, deleted marker, or audit tables.
- Hard delete removes the row from `users` and removes related rows from `user_roles`.

## Backend Contracts

- `public_user()` includes a public status field such as `isBanned`.
- `GET /api/admin/users` returns banned status for each user.
- Add an admin endpoint to set ban status for a non-admin user. A minimal shape is `PATCH /api/admin/users/{user_id}/ban` with `{"banned": true|false}`.
- Add `DELETE /api/admin/users/{user_id}` for hard deletion.
- Both new endpoints require `users:manage`.
- Both new endpoints reject admin targets with `409 Conflict` or another explicit client-visible error.
- Existing role update behavior remains unchanged.

## Authentication Flow

- Login rejects banned users after password verification and before issuing cookies.
- Refresh rejects banned users after resolving the refresh token user.
- `/api/auth/me` and all protected APIs reject banned users through `require_user()`.
- Deleted users already fail token-backed access because `get_user_by_id()` returns no row; deletion must also clean `user_roles`.

## Frontend Behavior

- The admin user row displays normal vs banned status.
- Non-admin rows show ban/unban and delete controls.
- Admin rows do not expose ban/delete controls.
- Delete uses a native confirmation step before calling the backend.
- On success, refresh the admin users state and show the existing toast feedback.
- On backend rejection, reload admin state and show the backend error.

## Compatibility

- Existing users default to not banned.
- Existing JWTs for a user become ineffective immediately after the user is banned because `require_user()` rechecks the database row on protected requests.
- A hard-deleted username can be registered again because no tombstone is retained.

## Rollback Notes

- The ban status column is additive and safe to leave in place.
- If delete behavior causes issues, the `DELETE /api/admin/users/{user_id}` route and UI control can be removed without changing existing auth flows.
