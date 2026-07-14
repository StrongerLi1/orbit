# Orbit 共享图书馆实施计划

## Preconditions

- 用户审阅并批准 `prd.md` 与 `design.md`。
- 运行 `task.py start` 后进入实现阶段。
- 通过 `trellis-before-dev` 加载 backend、frontend 与跨层规范。

## Implementation checklist

1. Configuration and permissions
   - Add storage directory, 100 MB book limit, and 5 MB cover limit settings.
   - Add `python-multipart` to backend dependencies.
   - Add `library:read`, `library:upload`, and `library:manage` to RBAC defaults and tests.
   - Document environment variables and Nginx body-size requirement.

2. Database and repository
   - Create `books` and `book_reads` tables and indexes idempotently.
   - Add row mappers and repository functions for book summaries, reader aggregation, CRUD, and per-user record ownership.
   - Extend user deletion to remove that user's reading records while retaining shared books.
   - Verify aggregate counts with multiple reads by the same and different users.

3. Secure file helpers
   - Create storage roots on startup.
   - Implement normalized internal names, safe path resolution, chunked temporary writes, size enforcement, and cleanup.
   - Validate EPUB/PDF/MOBI/AZW3/TXT and JPEG/PNG/WebP signatures with the standard library.
   - Implement attachment filename normalization and streaming responses.
   - Parse conservative filename patterns, EPUB OPF metadata/cover, and PDF document metadata.
   - Resolve manual input before embedded metadata and filename fallbacks.

4. Backend APIs
   - Add list/upload/admin-edit/admin-delete/download/cover endpoints.
   - Add list/create/update/delete reading-history endpoints.
   - Apply login, permission, ownership, date, and not-found checks consistently.
   - Ensure delete and failed upload paths clean database and filesystem state.

5. Frontend page
   - Add shared-library navigation and page markup.
   - Add state loading and card rendering with placeholder covers.
   - Add upload form using `FormData`, supported-format hints, disabled/loading states, and errors.
   - Add reading-date creation plus grouped reader-history UI with own-record edit/delete actions.
   - Add admin-only metadata/cover edit and book deletion controls.
   - Add responsive grid, cover aspect ratio, focus states, empty states, and mobile behavior.
   - Prefill title/author from the chosen filename without overwriting later user edits.

6. Tests and regression
   - Add tests for RBAC mappings and login requirements.
   - Add tests for file signatures, size limits, safe paths, cleanup, and filename normalization.
   - Add repository/API tests for shared visibility, admin-only mutations, multiple read records, aggregation, own-record update/delete, and cross-user denial.
   - Exercise upload, download, reader display, date correction, record deletion, and admin deletion in a browser.
   - Run the full existing test suite and syntax checks.

## Validation commands

```bash
npm test
python3 -m compileall backend run.py tests
node --check public/app.js
python3 tests/test_rbac.py
python3 tests/test_library.py
```

Browser validation should cover desktop and mobile widths with two normal users and one administrator.

## 2026-07-14 metadata enhancement result

- [x] Browser filename preview supports `《书名》 作者` and `书名 - 作者` without overwriting fields the user edited.
- [x] Upload resolves manual fields before embedded EPUB/PDF metadata and filename fallback.
- [x] EPUB title, creator, and bounded JPEG/PNG/WebP cover extraction are implemented; manual cover wins.
- [x] Malformed/missing embedded metadata falls back without rejecting a valid ebook.
- [x] `npm test`, `pip check`, OpenAPI multipart assertions, JavaScript syntax, and local browser form checks pass.
- [x] Production deployment completed on `123.56.29.242` with rollback backup `/opt/orbit-backups/20260714-150706-library-metadata`.

## Risk and rollback points

- File/database consistency: keep upload and delete cleanup localized; stop if a failure leaves untracked files.
- Authorization: verify UI visibility and backend enforcement separately; backend results are authoritative.
- Large uploads: verify application and Nginx limits together before production rollout.
- Existing account deletion: confirm reading-history cleanup does not delete shared books.
- Rollback by reverting application code while preserving new tables and storage; do not delete uploaded files during rollback.

## Review gate before start

- Confirm shared visibility, all-user upload, admin-only book management, multi-read history, own-record mutation, supported formats, size limits, and reader statistics match the approved PRD.
- Confirm no external book-source or Hermes-skill work remains in scope.
