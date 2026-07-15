# Shared Library Contract

> Cross-layer contracts for shared ebooks and per-user reading history.

## Scenario: Shared Catalog With Isolated Reading History

### 1. Scope / Trigger

- Trigger: Any change to shared-library routes, ebook storage, `books` / `book_reads`, library RBAC, or the library page.
- Book files and metadata are shared by authenticated users. Reading records are user-owned, but usernames and read dates are visible to authenticated library readers.

### 2. Signatures

```text
GET|POST   /api/library/books
PATCH|DELETE /api/library/books/{book_id}
GET        /api/library/books/{book_id}/download
GET        /api/library/books/{book_id}/cover
GET|POST   /api/library/books/{book_id}/reads
PATCH|DELETE /api/library/books/{book_id}/reads/{read_id}
GET|POST   /api/library/books/{book_id}/reviews
DELETE     /api/library/books/{book_id}/reviews/{review_id}
```

```sql
books(id, title, author, file_format, original_filename, stored_filename,
      file_size, cover_filename, cover_content_type, uploaded_by,
      uploaded_by_name, created_at, updated_at)
book_reads(id, book_id, user_id, read_date, created_at, updated_at)
book_reviews(id, book_id, user_id, reviewer_name, content, created_at)
```

```python
detect_book_format(path, original_filename) -> str
detect_cover(path) -> tuple[str, str]
metadata_from_filename(original_filename) -> {title: str, author: str}
extract_book_metadata(path, original_filename, file_format, max_cover_bytes) -> dict
list_books(current_user_id) -> list[dict]
list_book_reads(book_id, current_user_id) -> dict
list_book_reviews(book_id, current_user_id, is_admin) -> list[dict]
create_book_review(book_id, user_id, reviewer_name, content) -> dict
delete_book_review(book_id, review_id, user_id, is_admin) -> bool
```

### 3. Contracts

- `library:read` covers catalog, cover, download, and reading-history access; `library:upload` covers upload; `library:manage` covers shared metadata and book deletion.
- Default users receive `library:read` and `library:upload`; only administrators receive `library:manage` through the fixed-role seed.
- Upload is multipart with required `bookFile` and optional `title`, `author`, and `coverFile`. Admin edits still require `title` and `author`.
- Metadata priority is manual form value, then embedded EPUB/PDF metadata, then filename. Filename parsing recognizes `《书名》 作者` and `书名 - 作者`; otherwise the full stem is the title.
- EPUB parsing uses bounded XML reads and may extract a manifest cover image. A manually uploaded JPEG/PNG/WebP cover always overrides the embedded EPUB cover. PDF extraction reads title/author only; MOBI/AZW3/TXT use filename fallback.
- Filename values shown by the browser are automatic previews, not manual overrides: unchanged preview values are sent blank so embedded metadata retains priority; edited values are submitted normally.
- Books accept EPUB, PDF, MOBI, AZW3, or UTF-8 TXT up to `LIBRARY_MAX_FILE_MB` (default 100). Covers accept JPEG, PNG, or WebP up to `LIBRARY_MAX_COVER_MB` (default 5).
- `LIBRARY_STORAGE_DIR` is private storage with `books/`, `covers/`, and `tmp/`; it must not be served as a static directory.
- Internal stored names are generated IDs. User filenames are used only after normalization for `Content-Disposition`.
- `currentUserRead` is derived from whether the current user has at least one record. Re-reading always inserts another record; there is no `(book_id, user_id, read_date)` uniqueness constraint.
- Catalog statistics are `COUNT(DISTINCT user_id)` as `readerCount` and `COUNT(*)` as `readCount`.
- Reader responses expose usernames and dates, never user IDs. Only the record owner can update or delete a reading record.
- Book reviews are independent of reading records. Any authenticated library reader may create a review whether or not they have a reading record; a review stores the author UID plus a username snapshot and may be repeated for the same user/book.
- Review responses expose `id`, `username`, `content`, `createdAt`, and server-computed `canDelete`; they never expose the author UID. Only the review owner or a user with `users:manage` may delete a review.
- `POST /api/library/books/{book_id}/reviews` accepts `{ "content": string }`; content is trimmed, required, and limited to 3000 characters. `POST .../reads` also accepts optional `{ "review": string }`; when non-empty, the read and independent review are inserted in one transaction. Updating a read date never changes a review.
- Deleting a book removes its metadata, all reading records, reviews, ebook, and cover. Deleting a user removes that user's reading records and reviews but retains uploaded shared books.

### 4. Validation & Error Matrix

- Missing permission -> `403`; missing or invalid login -> `401`.
- If all metadata sources leave title or author empty -> `422` with a prompt to enter the missing value manually. Invalid ISO calendar date -> `422`.
- Book or cover over its configured limit -> `413`.
- Unsupported extension or mismatched file signature -> `415`.
- Missing book/file/cover -> `404`.
- Reading-record update/delete by a different user -> `404` to avoid disclosing ownership.
- Empty or overlong review -> `422`; deleting another user's review as a non-admin -> `404`.
- Any failed upload -> no database row, final file, or temporary part file remains.

### 5. Good/Base/Bad Cases

- Good: Stream an upload to a random temporary file, validate the complete content, atomically move it, then create metadata with compensating cleanup on failure.
- Good: Prefill from the filename immediately, but let the server replace unchanged previews with trusted embedded EPUB/PDF metadata.
- Good: Return grouped readers with an `isCurrentUser` marker so the UI renders edit/delete only for owned records.
- Good: Render review deletion from the API's `canDelete` flag while keeping owner/admin enforcement in the backend.
- Base: A book without a cover returns `404` from the cover route and renders a deterministic CSS placeholder.
- Base: Editing a reading date leaves all independent reviews unchanged; an optional review on a new read creates one additional review.
- Base: Malformed or absent embedded metadata is a soft failure and falls back to filename/manual input without rejecting an otherwise valid ebook.
- Bad: Use the original filename as a storage path or expose `LIBRARY_STORAGE_DIR` under `/public`.
- Bad: Submit filename-prefilled fields as manual values; this silently defeats embedded metadata priority.
- Bad: Store a single boolean `read` on `books`; it cannot isolate users or represent rereads.

### 6. Tests Required

- RBAC: default-user and admin permission membership.
- Files: supported signatures, disguised files, invalid UTF-8 beyond the first chunk, size limits, safe paths, and normalized download names.
- Metadata: filename patterns, EPUB title/creator/cover, PDF title/author, malformed metadata fallback, and cover-size bounds.
- Upload: successful file placement, manual-field/manual-cover precedence, embedded metadata/cover fallback, and cleanup when metadata creation fails.
- Repository: distinct-reader count, total-read count, current-user count, and grouped multi-read history.
- API: strict dates, authenticated access, admin-only shared mutations, owner-only record update/delete, and hidden cross-user records.
- Reviews: authenticated unread/read users can create; list hides UIDs; owner deletion, admin deletion, empty/overlong validation, and read+review atomic creation are covered.
- Browser: desktop and mobile grids, no horizontal overflow, filters, upload modal, grouped readers, and own-record editing.

### 7. Wrong vs Correct

#### Wrong

```python
target = settings.library_storage_dir / upload.filename
data = await upload.read()
```

This trusts a user-controlled path and loads a 100 MB file into memory.

#### Correct

```python
temporary = temporary_path()
await save_upload(upload, temporary, max_bytes, "电子书")
file_format = detect_book_format(temporary, upload.filename or "")
move_into_place(temporary, book_path(f"{book_id}.{file_format}"))
```

This keeps paths server-controlled, validates content, and uses bounded-memory streaming.

For automatic fields, do not treat the browser preview as user intent:

```javascript
// Wrong: filename preview always suppresses embedded metadata.
data.set('title', titleInput.value);

// Correct: only an edited value is a manual override.
if (titleInput.value === titleInput.dataset.autoValue) data.set('title', '');
```
