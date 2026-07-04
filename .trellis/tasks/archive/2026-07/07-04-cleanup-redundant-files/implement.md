# Clean Local And Server Redundant Files Implementation Plan

## Checklist

1. Planning
   - [x] Create Trellis task.
   - [x] Scan local workspace in read-only mode.
   - [x] Scan server `/opt/orbit` in read-only mode.
   - [x] Classify deletion candidates.
   - [x] Get user approval for the exact deletion set.

2. Local cleanup after approval
   - [x] Delete approved `.DS_Store` files.
   - [x] Delete approved local `__pycache__/` directories.
   - [x] Delete `.venv-fastapi/` only if explicitly approved. Not approved; kept.
   - [x] Re-run `git status --short --ignored` and confirm no unexpected source deletions.

3. Server cleanup after approval
   - [x] Delete approved server cache directories.
   - [x] Delete approved server backup files only if explicitly approved. Not approved; kept.
   - [x] Delete server `/opt/orbit/.trellis/` only if explicitly approved. Not approved; kept.
   - [x] Verify `systemctl is-active orbit`.
   - [x] Re-list selected paths to confirm removal.

## Completion Notes

- User selected option A: recommended minimal deletion set only.
- Local approved `.DS_Store` files and app-level Python caches were removed.
- Server approved cache directories were removed.
- Server verification returned `orbit` service status `active`.
- Server spot check confirmed `/opt/orbit/.venv` and `/opt/orbit/data/db.json` remained present.
- Optional candidates were intentionally kept: local `.venv-fastapi/`, server `/opt/orbit/.trellis/`, and server backup files under `/opt/orbit/data/`.

## Proposed Deletion Set For Approval

Recommended minimal deletion set:

- Local:
  - `.DS_Store`
  - `.trellis/.DS_Store`
  - `.trellis/spec/.DS_Store`
  - `.trellis/tasks/.DS_Store`
  - `.trellis/tasks/archive/.DS_Store`
  - `.trellis/tasks/archive/2026-07/.DS_Store`
  - `.trellis/workspace/.DS_Store`
  - `__pycache__/`
  - `backend/__pycache__/`
  - `tests/__pycache__/`
  - `.trellis/scripts/common/__pycache__/`
- Server:
  - `/opt/orbit/.cache/`
  - `/opt/orbit/__pycache__/`
  - `/opt/orbit/backend/__pycache__/`
  - `/opt/orbit/tests/__pycache__/`

Optional deletion set requiring explicit confirmation:

- Local:
  - `.venv-fastapi/`
- Server:
  - `/opt/orbit/.trellis/`
  - `/opt/orbit/data/db.json.backup-20260623-0012`
  - `/opt/orbit/data/db.json.backup-20260623-0031`
  - `/opt/orbit/data/db.json.backup-20260627-225226-fastapi-mysql`
  - `/opt/orbit/data/mysql-backup-before-auth-20260703-233120.sql`
  - `/opt/orbit/data/mysql-backup-before-jwt-20260704-000536.sql`

## Validation Commands

- Local: `git status --short --ignored`
- Local: `find . -path './.git' -prune -o \( -name '.DS_Store' -o -name '__pycache__' \) -print`
- Server: `systemctl is-active orbit`
- Server: `find /opt/orbit -maxdepth 3 -type d \( -name __pycache__ -o -name .cache \) -print`

## Risk Notes

- Do not use `git clean -fdx`; it would remove important untracked Trellis/Codex workflow files.
- Do not delete `/opt/orbit/.venv/`; production starts Python from there.
- Do not include secret values in logs, task artifacts, or summaries.
