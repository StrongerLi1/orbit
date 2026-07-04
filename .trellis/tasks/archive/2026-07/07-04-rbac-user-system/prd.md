# Implement RBAC user system

## Goal

Upgrade Orbit from a boolean `admin` flag to a role-based access control user system that can be developed locally, documented, pushed to GitHub, and deployed to the existing server without breaking the current admin login.

The target outcome is a complete but minimal RBAC system: roles, permissions, user-role assignment, admin-only user/role management, authorization checks on protected APIs, migration from the existing `users.is_admin`, updated developer documentation, and verified production rollout.

## Confirmed Facts

- The current backend is FastAPI with MySQL and Redis-backed dual JWT auth.
- The current frontend is plain HTML/CSS/JavaScript with hash routes.
- User accounts are stored in the MySQL `users` table with `is_admin TINYINT(1)`.
- JWT payloads and `public_user()` currently expose `isAdmin`.
- Existing business APIs only call `require_user(request)` and do not differentiate read/write/admin access.
- Current data tables (`bookmarks`, `todos`, `plans`, `folders`, `excerpts`) do not have `user_id`; all logged-in users share the same data.
- The deployed service runs from `/opt/orbit` behind Nginx with systemd service `orbit`; Redis and MySQL are already on the server.
- Existing documentation for authentication lives in `docs/auth-system.md`.
- Existing verification is mostly command-level: `npm test` runs `python3 -m compileall backend run.py`; auth docs include manual curl checks.

## Requirements

- Preserve the existing admin account and map any `users.is_admin = 1` user to the administrator role during migration.
- Add RBAC schema support for roles, permissions, and user-role assignments.
- Seed default roles and permissions at startup in an idempotent way.
- Keep compatibility for existing clients by continuing to return `isAdmin` while also exposing role/permission information.
- Add backend authorization helpers so routes can require specific permissions instead of checking raw role names.
- Add admin-only APIs for listing users, changing user roles, listing roles, and listing permissions.
- Add an admin UI where administrators can inspect users, inspect fixed roles/permissions, and assign fixed roles to users.
- Do not include UI support for creating custom roles or editing role-permission matrices in this version.
- Restrict user/role administration to administrators.
- Prevent ordinary users from escalating their own privileges.
- Keep existing business data shared across all logged-in users for this version.
- Keep the existing public registration flow; newly registered users receive the fixed `user` role.
- Use the first-version permission set:
  - `content:read` for reading shared Orbit business data.
  - `content:write` for creating, updating, and deleting shared Orbit business data.
  - `netdisk:search` for using PanSou search.
  - `users:manage` for managing users and user role assignments.
  - `roles:manage` for managing roles and role permissions.
- Seed default roles:
  - `admin` has all permissions.
  - `user` has `content:read`, `content:write`, and `netdisk:search`.
- Update development documentation to describe the RBAC schema, APIs, migration behavior, local verification, and production deployment notes.
- Push completed code to the GitHub remote after verification.
- Deploy to the existing server after verification and confirm the production service is healthy.

## Acceptance Criteria

- [x] Existing admin login still works after migration and deployment.
- [x] Existing `is_admin = 1` users receive the admin role automatically.
- [x] Ordinary users cannot call admin-only APIs.
- [x] Default `user` role can use existing shared business features and netdisk search.
- [x] Default `admin` role can use all features and RBAC administration.
- [x] Public registration remains available and assigns the `user` role by default.
- [x] Admin users can list users and change another user's roles from the UI.
- [x] Admin UI shows the fixed default roles and permissions without allowing role schema edits.
- [x] Admin users cannot accidentally remove their own last effective admin access without an explicit server-side guard.
- [x] JWT refresh/login returns enough public user data for the frontend to show admin-only UI.
- [x] Business APIs remain shared across logged-in users in this version.
- [x] `npm test` passes.
- [x] Manual auth/RBAC curl checks pass locally or against the deployed server.
- [x] Documentation is updated.
- [x] Changes are pushed to GitHub.
- [x] Production deployment completes and `orbit` is healthy.

## Notes

- This is a complex task; `design.md` and `implement.md` are required before implementation starts.
- Do not record server credentials, database passwords, JWT secrets, or admin passwords in task artifacts or docs.
- Deferred: per-user/private business data spaces are explicitly out of scope for this RBAC rollout.
- Security trade-off accepted for this version: public registration plus shared business data means any registered ordinary user can see and modify the shared Orbit content.

## Post-Completion Verification

- Production deployment verification passed after commit `3d01e04`: `orbit` service active, unauthenticated admin API returned 401, admin login returned RBAC fields, `/api/admin/users` and `/api/admin/roles` returned 200, temporary ordinary user received `user` role and was denied admin API with 403.
- Local MySQL verification was completed after the local `orbit` database became available: `initialize_database()` created/updated `roles`, `permissions`, `role_permissions`, and `user_roles`; default counts were 2 roles and 5 permissions; local API checks passed for unauthenticated 401, temporary admin RBAC login, admin user/role APIs, temporary ordinary user shared-content access, and ordinary-user admin 403. Temporary local verification users were cleaned up.
