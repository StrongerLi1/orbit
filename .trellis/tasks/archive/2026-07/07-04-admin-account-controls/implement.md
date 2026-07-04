# Admin account deletion and ban controls implementation plan

## Checklist

- Update `backend/database.py` to add an idempotent `users.is_banned` column with default `0`.
- Update `backend/auth.py`:
  - Include ban status in `public_user()`.
  - Add helpers for checking whether a target user is an admin.
  - Add a helper to ban/unban a non-admin user.
  - Add a helper to hard-delete a non-admin user and remove `user_roles`.
  - Make `require_user()` reject banned users.
  - Make `refresh_user()` reject banned users.
- Update `backend/main.py`:
  - Make login reject banned users before issuing cookies.
  - Add `PATCH /api/admin/users/{user_id}/ban`.
  - Add `DELETE /api/admin/users/{user_id}`.
- Update `public/app.js`:
  - Render banned status in the admin user list.
  - Add ban/unban and delete controls for non-admin users.
  - Add native confirmation before delete.
  - Update admin state after ban/unban/delete.
- Update `public/styles.css` for compact account status/actions inside existing admin rows.
- Update docs:
  - `README.md` API list.
  - `docs/auth-system.md` user schema, auth flow, and admin API section.
- Update tests in `tests/test_rbac.py` or add adjacent lightweight tests for public user status and admin safety helper behavior where practical.

## Validation

- Run `npm test`.
- If local MySQL/Redis are available, run a manual smoke check:
  - Admin can see user management.
  - Admin can ban a non-admin user.
  - Banned user cannot log in.
  - Banned user can be unbanned and log in again.
  - Admin can delete a non-admin user after confirming.
  - Deleted username can register again.
  - Attempts to ban or delete an admin account fail.

## Risk Points

- Startup schema update must be idempotent on both fresh and existing MySQL databases.
- Banned users with existing access tokens must fail through `require_user()`, not only through login.
- Admin protection must be backend-enforced because frontend hiding is not security.
