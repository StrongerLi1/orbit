# Admin account deletion and ban controls

## Goal

Allow administrators to ban and delete non-admin user accounts from the existing user management surface, while preventing any admin account from being banned or deleted.

## Background

- The product already has JWT + Redis authentication and fixed RBAC roles in `backend/auth.py`.
- The existing admin APIs in `backend/main.py` support listing users, listing roles/permissions, and patching user roles.
- The existing admin page in `public/app.js` renders users and role checkboxes, but has no account status, ban action, or delete action.
- `users:manage` is the existing permission used for user administration.
- The `users` table currently has `id`, `username`, `password_hash`, `is_admin`, `created_at`, and `last_login_at`; it has no ban/deleted/status field.
- User role assignments live in `user_roles`, so account deletion must clean up related rows or otherwise avoid orphaned role assignments.
- The current login, refresh, and authenticated request paths only check that the user exists and the token is valid; they do not check account status.

## Requirements

- Administrators with `users:manage` can ban a non-admin account.
- Administrators with `users:manage` can unban a banned non-admin account.
- Administrators with `users:manage` can delete a non-admin account.
- Admin accounts cannot be banned or deleted through the new controls or APIs.
- Banned users cannot log in, refresh sessions, use `/api/auth/me`, or access protected business APIs.
- Bans are indefinite until an administrator unbans the account.
- The admin user list shows enough account status to distinguish normal and banned users.
- The UI gives administrators explicit controls for ban/unban and delete actions for non-admin accounts.
- The UI requires a confirmation step before hard-deleting an account.
- Deleting an account removes its role assignments.
- Deleting an account hard-deletes the `users` row.
- Hard-deleted usernames are released for future registration.
- Ban status is a simple indefinite on/off status, with no reason field and no expiration date.

## Acceptance Criteria

- [ ] A `users:manage` administrator can ban a non-admin user from the admin page.
- [ ] A `users:manage` administrator can unban a banned non-admin user from the admin page.
- [ ] A `users:manage` administrator can delete a non-admin user from the admin page only after confirming the destructive action.
- [ ] Attempts to ban, unban, or delete an admin account are rejected by the backend.
- [ ] A banned user receives an authentication failure when logging in or refreshing an existing session.
- [ ] A banned user with an existing access token can no longer access protected APIs.
- [ ] Deleted users can no longer authenticate because their `users` row is gone, and their `user_roles` rows are removed.
- [ ] A hard-deleted username can be registered again.
- [ ] The user management UI refreshes after ban/unban/delete and shows clear errors when an operation is rejected.

## Out Of Scope

- Banning or deleting admin accounts.
- Creating custom roles or editing the permission matrix.
- Per-user ownership or deletion of shared business data.
- Ban reasons, ban history, audit log, and automatic ban expiration.
