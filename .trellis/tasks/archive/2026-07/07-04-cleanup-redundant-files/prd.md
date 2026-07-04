# Clean local and server redundant files

## Goal

Clean redundant files in `/Users/king/Documents/code/a` and the deployed Orbit server directory without deleting source code, active runtime dependencies, production data, or private configuration.

The cleanup must be evidence-based: scan first, classify candidates by risk, get explicit approval for the deletion set, then delete only the approved paths and verify the local repo and production service still look healthy.

## Confirmed Facts

- Local workspace: `/Users/king/Documents/code/a`.
- Server host is recorded in Trellis workspace notes; deployed app path is `/opt/orbit`.
- Production service uses systemd service `orbit` with `WorkingDirectory=/opt/orbit` and `ExecStart=/opt/orbit/.venv/bin/python /opt/orbit/run.py`.
- Production `/opt/orbit` is about 63M. The server virtualenv `/opt/orbit/.venv` is about 62M and is required by the running service.
- Local repo has many untracked Trellis/Codex files that are operational project files, not deletion candidates.
- `git clean -ndx` would list important untracked directories such as `.agents/`, `.codex/`, `.trellis/scripts/`, `.trellis/tasks/`, and `.trellis/workspace/`; these must not be deleted as generic "untracked" files.
- Local clear low-risk cleanup candidates found:
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
- Local medium-risk cleanup candidate found:
  - `.venv-fastapi/` is about 26M. It is reproducible from `requirements.txt`, but deleting it removes the current local Python environment.
- Server clear low-risk cleanup candidates found:
  - `/opt/orbit/.cache/`
  - `/opt/orbit/__pycache__/`
  - `/opt/orbit/backend/__pycache__/`
  - `/opt/orbit/tests/__pycache__/`
- Server medium-risk cleanup candidates found:
  - `/opt/orbit/data/db.json.backup-20260623-0012`
  - `/opt/orbit/data/db.json.backup-20260623-0031`
  - `/opt/orbit/data/db.json.backup-20260627-225226-fastapi-mysql`
  - `/opt/orbit/data/mysql-backup-before-auth-20260703-233120.sql`
  - `/opt/orbit/data/mysql-backup-before-jwt-20260704-000536.sql`
  - `/opt/orbit/.trellis/`
- Server must-keep paths include:
  - `/opt/orbit/.venv/`
  - `/opt/orbit/data/db.json`
  - application source files used by the service
  - systemd service configuration
  - private credentials and secrets

## Requirements

- Do not delete anything until the exact deletion set has been presented to and approved by the user.
- Do not delete tracked source files or active uncommitted user work.
- Do not delete Trellis/Codex operational files just because they are untracked by git.
- Do not copy secrets, passwords, JWT values, or private service environment values into task artifacts, commits, or user-facing summaries.
- Treat production cleanup as higher risk than local cleanup.
- Keep the production service dependency `/opt/orbit/.venv/`.
- Keep current production data unless the user explicitly approves deleting a specific backup or data file.
- Prefer deleting obvious generated files first: `.DS_Store`, `__pycache__`, `.pyc`, and cache directories.
- For server backup files, either keep the latest migration-relevant backup or delete only after explicit user approval.

## Acceptance Criteria

- [x] Local deletion candidates are listed and classified before deletion.
- [x] Server deletion candidates are listed and classified before deletion.
- [x] User approves the final deletion set.
- [x] Approved local paths are deleted, and no unrelated untracked Trellis/Codex/project files are removed.
- [x] Approved server paths are deleted, and `/opt/orbit/.venv/` plus current production data remain in place.
- [x] Post-cleanup verification confirms the local git status does not show unexpected source deletions.
- [x] Post-cleanup verification confirms production `orbit` service is still active.

## Notes

- Private deployment access details are kept in the ignored local Trellis workspace secret note and are intentionally not repeated here.
