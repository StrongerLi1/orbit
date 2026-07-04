# RBAC User System Design

## Scope

This task upgrades Orbit authentication from a boolean admin flag to a minimal complete RBAC architecture. The rollout keeps current shared business data behavior and public registration.

Out of scope:

- Per-user/private business data.
- Custom role creation or role-permission editing in the UI.
- Device/session management beyond the existing Redis refresh-token flow.

## Current Architecture

- `backend/auth.py` owns password hashing, JWT signing, refresh-token Redis state, user lookup, and public user serialization.
- `backend/database.py` creates MySQL tables at startup and seeds the configured admin user.
- `backend/main.py` protects business APIs with `require_user(request)`.
- `public/app.js` stores the current user in `state.user`, renders the app, and retries failed requests through `/api/auth/refresh`.

Current authorization is `users.is_admin`; it appears in database rows, JWT payloads, `public_user()`, and the frontend chip.

## Data Model

Add three RBAC tables:

```sql
roles (
  id VARCHAR(64) PRIMARY KEY,
  name VARCHAR(64) NOT NULL UNIQUE,
  description VARCHAR(255) NOT NULL
)

permissions (
  id VARCHAR(64) PRIMARY KEY,
  name VARCHAR(80) NOT NULL UNIQUE,
  description VARCHAR(255) NOT NULL
)

role_permissions (
  role_id VARCHAR(64) NOT NULL,
  permission_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (role_id, permission_id)
)

user_roles (
  user_id VARCHAR(64) NOT NULL,
  role_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (user_id, role_id)
)
```

Keep `users.is_admin` for compatibility during this version. It remains a legacy mirror used to seed/migrate admin membership and preserve older docs/scripts.

Default permissions:

- `content:read`
- `content:write`
- `netdisk:search`
- `users:manage`
- `roles:manage`

Default roles:

- `admin`: all permissions.
- `user`: `content:read`, `content:write`, `netdisk:search`.

Startup initialization is idempotent:

1. Create RBAC tables if missing.
2. Upsert fixed permissions and roles.
3. Upsert fixed role-permission mappings.
4. Assign `admin` to every `users.is_admin = 1` user.
5. Assign `user` to users without any role.
6. Seed configured `ADMIN_USERNAME` as admin.

## Backend Contracts

Public user response should keep existing fields and add RBAC fields:

```json
{
  "id": "uuid",
  "username": "admin",
  "isAdmin": true,
  "roles": ["admin"],
  "permissions": ["content:read", "content:write", "netdisk:search", "users:manage", "roles:manage"],
  "createdAt": "...",
  "lastLoginAt": "..."
}
```

`isAdmin` is derived from effective roles/permissions where possible, with `users.is_admin` kept as a compatibility fallback.

Authorization helpers:

- `require_user(request)` continues to return the database user row with effective `roles` and `permissions` attached.
- `require_permission(request, permission)` returns the user or raises 403.
- Route code checks permissions, not role names.

Business route mapping:

- `GET /api/{collection}` requires `content:read`.
- `POST/PATCH/DELETE /api/{collection}` requires `content:write`.
- `GET /api/netdisk/search` requires `netdisk:search`.
- Auth endpoints remain public except `/me`, `/refresh`, and `/logout`, which keep their existing login requirements.

Admin APIs:

- `GET /api/admin/users` requires `users:manage`; returns users with roles and permission summaries.
- `PATCH /api/admin/users/{user_id}/roles` requires `users:manage`; accepts `{"roles":["admin"|"user"]}`.
- `GET /api/admin/roles` requires `roles:manage`; returns fixed roles with permissions.
- `GET /api/admin/permissions` requires `roles:manage`; returns fixed permissions.

Server-side guard:

- Role assignment must reject unknown roles.
- Role assignment must require at least one role.
- Role assignment must prevent removing the last effective admin. The simplest guard is to reject updates that would leave zero users with the `admin` role.
- The updated legacy `users.is_admin` should mirror whether the user has the `admin` role.

## Frontend Contract

`state.user.permissions` controls UI visibility:

- Show admin navigation only when `users:manage` or `roles:manage` is present.
- Admin page lists users, their current roles, and fixed role descriptions.
- Admin can assign fixed roles through checkboxes or a select control.
- Ordinary users do not see the admin page link; direct hash navigation still relies on backend 403 for enforcement.

Keep the frontend in `public/app.js` / `public/index.html` unless the implementation becomes unreasonably large. The project currently favors a compact vanilla frontend over a component hierarchy.

## Migration And Compatibility

- Existing admin users keep admin access because `is_admin = 1` maps to the `admin` role at startup.
- Existing ordinary users get the `user` role.
- Existing access/refresh tokens issued before the RBAC rollout may contain only `isAdmin`; `require_user()` re-reads the user from MySQL and attaches effective roles, so authorization should not trust token permissions.
- After role changes, existing access tokens may continue until expiry, but backend authorization re-checks database roles on each request, so permission changes take effect immediately for API checks.

## Deployment

Deployment uses the existing GitHub remote and server layout recorded in Trellis workspace notes:

- Push verified code to `origin`.
- SSH to the server using local secret notes only; do not commit or print secrets.
- Update `/opt/orbit`.
- Restart the `orbit` systemd service.
- Confirm service health and at least one RBAC-protected endpoint.

## Rollback

Primary rollback is git-based:

- Keep `users.is_admin` intact.
- RBAC tables are additive.
- If deployment fails, revert the app code to the previous commit and restart `orbit`.
- Additive RBAC tables can remain unused during rollback.

