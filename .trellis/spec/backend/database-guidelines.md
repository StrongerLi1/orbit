# Database Guidelines

> Database patterns and conventions for this project.

---

## Overview

<!--
Document your project's database conventions here.

Questions to answer:
- What ORM/query library do you use?
- How are migrations managed?
- What are the naming conventions for tables/columns?
- How do you handle transactions?
-->

(To be filled by the team)

---

## Query Patterns

<!-- How should queries be written? Batch operations? -->

(To be filled by the team)

---

## Migrations

<!-- How to create and run migrations -->

(To be filled by the team)

---

## Naming Conventions

<!-- Table names, column names, index names -->

(To be filled by the team)

---

## Common Mistakes

<!-- Database-related mistakes your team has made -->

(To be filled by the team)

## Scenario: Fixed RBAC Startup Schema

### 1. Scope / Trigger

- Trigger: Any change to authentication, role assignment, permissions, or protected API behavior.
- RBAC is a cross-layer contract: MySQL tables -> `backend.auth` helpers -> FastAPI routes -> `public/app.js` admin UI.
- The project currently uses startup-time idempotent schema creation instead of a separate migration runner.

### 2. Signatures

Database tables:

```sql
roles(id, name, description)
permissions(id, name, description)
role_permissions(role_id, permission_id)
user_roles(user_id, role_id)
users.is_admin
```

Backend APIs:

```python
require_permission(request, "content:read")
require_permission(request, "content:write")
require_permission(request, "netdisk:search")
require_permission(request, "users:manage")
require_permission(request, "roles:manage")
```

Admin HTTP routes:

```text
GET /api/admin/users
PATCH /api/admin/users/{user_id}/roles
GET /api/admin/roles
GET /api/admin/permissions
```

### 3. Contracts

- Fixed roles are `admin` and `user`.
- Fixed permissions are `content:read`, `content:write`, `netdisk:search`, `users:manage`, and `roles:manage`.
- `admin` has every permission.
- `user` has `content:read`, `content:write`, and `netdisk:search`.
- `public_user()` must return `id`, `username`, `isAdmin`, `roles`, `permissions`, `createdAt`, and `lastLoginAt`.
- `isAdmin` remains a compatibility field, but new route checks must use permissions.
- `users.is_admin = 1` must migrate to the `admin` role during startup.
- Users without roles must receive the `user` role during startup.

### 4. Validation & Error Matrix

- Missing/invalid access token -> 401.
- Authenticated user missing a permission -> 403.
- `PATCH /api/admin/users/{id}/roles` with unknown role -> 422.
- `PATCH /api/admin/users/{id}/roles` with empty roles -> 422.
- Removing the last effective admin -> 409.
- Missing user for role update -> 404.

### 5. Good/Base/Bad Cases

- Good: Add a protected business write route with `require_permission(request, "content:write")`.
- Base: Keep `/api/auth/me` on `require_user()` because it only reports the current authenticated user.
- Bad: Check `row["is_admin"]` directly in a route or frontend branch for authorization.

### 6. Tests Required

- `npm test` must run compile checks and the RBAC self-check.
- RBAC self-check must assert fixed role/permission membership and `public_user()` compatibility fields.
- Deployment verification must include an admin login, `/api/auth/me`, `/api/admin/users`, `/api/admin/roles`, and a non-admin 403 check when a non-admin user is available.

### 7. Wrong vs Correct

#### Wrong

```python
if not user["is_admin"]:
    raise HTTPException(status_code=403, detail="Forbidden")
```

#### Correct

```python
require_permission(request, "users:manage")
```

This keeps authorization tied to the RBAC permission contract rather than the legacy admin mirror.
