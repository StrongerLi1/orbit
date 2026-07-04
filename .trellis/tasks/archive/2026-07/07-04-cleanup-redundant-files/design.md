# Clean Local And Server Redundant Files Design

## Boundaries

This task cleans generated and redundant files in two places:

- Local workspace: `/Users/king/Documents/code/a`.
- Server deployment directory: `/opt/orbit`.

The task does not refactor source code, change dependencies, rotate credentials, alter database schema, or redeploy the app.

## Deletion Classes

### Low Risk

Generated files that can be recreated automatically and are not source of truth:

- `.DS_Store`
- `__pycache__/`
- `.pyc`
- pip/cache directories outside active dependency directories

These are safe to delete after final user approval.

### Medium Risk

Files or directories that are probably redundant but may be useful for recovery or local convenience:

- Local `.venv-fastapi/`
- Server `/opt/orbit/data/*.backup*`
- Server `/opt/orbit/data/mysql-backup-before-*.sql`
- Server `/opt/orbit/.trellis/`

These require explicit path-level approval.

### Must Keep

Paths needed for current operation or project workflow:

- Local `.agents/`, `.codex/`, `.trellis/scripts/`, `.trellis/spec/`, `.trellis/tasks/`, `.trellis/workspace/`, and `AGENTS.md`.
- Server `/opt/orbit/.venv/`.
- Server current data file `/opt/orbit/data/db.json`.
- Application source, docs, tests, and runtime configuration used by systemd.

## Server Handling

Server actions must be performed through SSH using private local notes only. Commands must avoid echoing secret values. The `orbit` service should be checked after cleanup with `systemctl is-active orbit`.

No server deletion command should use a broad pattern rooted at `/opt/orbit` unless the target list was already generated and approved.

## Rollback

Low-risk generated files do not need rollback because they are recreated by Python, macOS, or package tooling.

Medium-risk files should only be deleted when either:

- The user accepts permanent removal, or
- They are copied to an approved external backup location first.

No database or production runtime state should be deleted in this task.
