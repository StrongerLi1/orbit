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

## Scenario: User-Scoped Todos and Plans

### 1. Scope / Trigger

- Trigger: Any change to `todos`, `plans`, generic collection CRUD, account deletion, JSON import, or dashboard/Android content loading.
- Isolation is a storage and API contract: authenticated UID -> repository owner predicate -> MySQL `owner_user_id` -> unchanged todo/plan response shape.

### 2. Signatures

```sql
todos.owner_user_id VARCHAR(64) NULL
plans.owner_user_id VARCHAR(64) NULL
INDEX idx_todos_owner_created (owner_user_id, created_at)
INDEX idx_plans_owner_created (owner_user_id, created_at)
```

```text
GET|POST              /api/todos
PATCH|DELETE          /api/todos/{id}
GET|POST              /api/plans
PATCH|DELETE          /api/plans/{id}
```

```python
USER_SCOPED_COLLECTIONS = frozenset({"todos", "plans"})
list_items(collection, current_user_id, is_admin=False)
get_item(collection, item_id, current_user_id, is_admin=False)
create_item(collection, item, current_user)
update_item(collection, item_id, item, current_user)
delete_item(collection, item_id, current_user)
```

### 3. Contracts

- `initialize_database()` adds both owner columns and owner/created indexes idempotently. After RBAC/admin seed, `backfill_legacy_owners()` assigns every empty legacy todo/plan owner to the configured admin, falling back to the first existing admin.
- JSON import writes legacy todo/plan rows with an empty owner only inside startup migration; the same startup then backfills them to the admin. Client payload owner fields are never trusted.
- All todo/plan list, lookup, update, and delete SQL includes the authenticated owner UID. `users:manage` does not bypass this filter: administrators also see and manage only their own rows.
- Update and delete keep `owner_user_id = current_user_id` in the mutation SQL, not only in a preceding lookup.
- Cross-user IDs behave as missing records (`404`) so ownership and existence are not disclosed.
- API response fields remain unchanged; browser and Android clients send no user parameter and derive dashboard/statistics from the already filtered collections.
- Hard account deletion removes that user's todos and plans; shared excerpts remain because they retain a display-name snapshot and separate ownership semantics.

### 4. Validation & Error Matrix

- Missing/invalid login -> existing `401`; missing `content:read` / `content:write` -> existing `403`.
- Repository todo/plan call without a current UID -> fail closed with `ValueError`; never fall back to an unfiltered query.
- Cross-user PATCH/DELETE -> `404`, with no mutation.
- Client-supplied `owner_user_id` or equivalent -> ignored by validation.
- Existing schema without owner columns/indexes -> startup adds them and preserves all rows.
- Empty legacy owner with no available admin -> remains inaccessible until an admin exists and startup reruns; never becomes globally visible.

### 5. Good/Base/Bad Cases

- Good: Bind owner from `require_permission(...)`'s authenticated user and reuse `USER_SCOPED_COLLECTIONS` for every generic CRUD branch.
- Base: An old deployment starts once, adds nullable owner columns, assigns historical rows to admin, and serves unchanged todo/plan JSON to existing clients.
- Bad: Filter only `GET /api/todos`; a user who knows another ID could still PATCH/DELETE it.

### 6. Tests Required

- Repository self-check: todo/plan list queries include owner UID; create inserts owner UID; update/delete SQL includes both record ID and owner UID.
- Validation self-check: forged owner fields do not survive todo/plan validation.
- Migration self-check/integration: empty owners for todos, plans, and excerpts backfill only to admin; non-empty owners remain unchanged; repeated startup is idempotent.
- Account deletion: private todos/plans are removed before the user row.
- Shared regression: `npm test`, browser JavaScript syntax, and Android `testDebugUnitTest lintDebug assembleDebug` when a compatible JDK and Android SDK are available.

### 7. Wrong vs Correct

#### Wrong

```python
cursor.execute("UPDATE todos SET completed = %s WHERE id = %s", (completed, item_id))
```

#### Correct

```python
cursor.execute(
    "UPDATE todos SET completed = %s WHERE id = %s AND owner_user_id = %s",
    (completed, item_id, current_user_id),
)
```

The mutation predicate is the final authorization boundary; client filtering and a preceding SELECT are not sufficient.
