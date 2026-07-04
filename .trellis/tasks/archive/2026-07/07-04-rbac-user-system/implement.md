# RBAC User System Implementation Plan

## Pre-Implementation

- [x] Read relevant backend/frontend files and docs before editing.
- [x] Load `trellis-before-dev` before code changes.
- [x] Confirm task status is moved to `in_progress` with `task.py start` only after planning review.

## Implementation Checklist

1. Database and auth core
   - [x] Add fixed role and permission constants in `backend/auth.py` or a minimal local helper.
   - [x] Create RBAC tables in `backend/database.py`.
   - [x] Add idempotent role/permission seeding and legacy `is_admin` migration.
   - [x] Add helpers to fetch user roles and permissions.
   - [x] Update `public_user()`, JWT base payload, `create_user()`, and admin seeding.

2. Authorization gates
   - [x] Add `require_permission()`.
   - [x] Change business routes from bare `require_user()` to permission checks.
   - [x] Add admin routes for users, roles, permissions, and role assignment.
   - [x] Add last-admin and unknown-role guards.

3. Frontend admin UI
   - [x] Add admin route/link visible only to users with admin permissions.
   - [x] Add state for admin users and roles.
   - [x] Render fixed roles and user role assignment controls.
   - [x] Handle 403 responses with a user-facing toast.

4. Documentation
   - [x] Update `docs/auth-system.md` with RBAC schema, API contracts, migration behavior, and verification.
   - [x] Update `README.md` API/auth summary if needed.

5. Verification
   - [x] Run `npm test`.
   - [x] Run local server or targeted curl checks when database/Redis are available.
   - [x] Verify ordinary user cannot call admin APIs.
   - [x] Verify admin can list users and update roles.
   - [x] Verify business APIs still work for default `user`.

6. GitHub and deployment
   - [x] Stage only relevant changes.
   - [x] Commit with a concise message.
   - [x] Push to `origin`.
   - [x] Deploy to the existing server.
   - [x] Confirm `orbit` service status and production endpoint behavior.

## Risk Points

- Startup ordering: admin seeding must happen after RBAC tables and fixed role mappings exist.
- Compatibility: `isAdmin` must remain in API responses while the frontend transitions to `permissions`.
- Shared data: public registration remains open, so new users can access shared business content by design.
- Deployment: server credentials and secrets must stay local and out of docs/commits.

## Validation Commands

```bash
npm test
```

Manual checks:

```bash
curl -i http://127.0.0.1:3000/api/admin/users
curl -c /tmp/orbit.cookie -H 'content-type: application/json' \
  -d '{"username":"admin","password":"<local password>"}' \
  http://127.0.0.1:3000/api/auth/login
curl -b /tmp/orbit.cookie http://127.0.0.1:3000/api/admin/users
curl -b /tmp/orbit.cookie http://127.0.0.1:3000/api/admin/roles
```

## Completed Validation

- `npm test` passed after RBAC implementation.
- `node --check public/app.js` passed.
- Production API validation passed after deployment.
- Local MySQL/API validation passed after the local database became available:
  - RBAC tables exist locally.
  - Default roles count is 2 and permissions count is 5.
  - Unauthenticated `/api/admin/users` returns 401.
  - Temporary admin can log in and receives `admin` role plus `users:manage`.
  - Temporary ordinary user receives `user`, can read `/api/bookmarks`, and gets 403 for `/api/admin/users`.
  - Temporary verification users were cleaned up.
