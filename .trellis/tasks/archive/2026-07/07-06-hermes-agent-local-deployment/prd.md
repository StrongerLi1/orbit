# Add Hermes agent local deployment

## Goal

Add a Hermes Agent capability to Orbit Personal Hub, validate it locally first, and require explicit user confirmation before any production deployment or push.

The first usable increment should let an authenticated Orbit user discover and operate a local Hermes Agent deployment from Orbit without vendoring the Hermes codebase into this repository.

## Confirmed Facts

- Orbit is a FastAPI backend with a static single-page frontend in `public/`.
- Runtime configuration is centralized in `backend/config.py` and `.env.example`.
- Authentication and RBAC are centralized in `backend/auth.py`; current user role permissions include shared content, netdisk search, folder management, and admin access.
- The main app starts through `npm start` -> `python3 run.py`; `server.js` is an older Node implementation and is not the primary backend path.
- Hermes Agent latest release found through GitHub is `v2026.7.1`, project version `0.18.0`.
- Hermes Agent is MIT licensed, Python-based, and supports CLI, gateway, dashboard, MCP, Docker Compose, and provider configuration.
- Hermes Agent README recommends the managed install one-liner for macOS/Linux and documents Docker Compose with a localhost-only dashboard.
- Hermes Agent stores configuration and runtime state under `~/.hermes` by default and may require LLM/tool API keys depending on chosen provider.
- Hermes Agent docs define `hermes dashboard` as the local web dashboard command, defaulting to `http://127.0.0.1:9119`.
- Hermes Agent CLI supports `hermes dashboard --status` and `hermes dashboard --stop`.
- The MVP decision is a local launcher/status/dashboard entry, not an embedded Orbit chat or API proxy.

## Requirements

- Add a local-only Hermes Agent integration path for Orbit.
- Protect Hermes management behind existing authentication and admin-only authorization.
- Keep Hermes as an external dependency/process; do not copy Hermes source into this repository.
- Provide configuration knobs for the local Hermes dashboard URL, command, and timeout through environment variables and `.env.example`.
- Surface a small admin-only frontend experience in Orbit for Hermes status, start, stop, refresh, and opening the dashboard.
- Return clear unavailable/error states when Hermes is not installed, not configured, or not reachable.
- Run and verify locally before asking about production deployment.
- Do not deploy, push, or create a PR until the user explicitly confirms after local validation.

## Acceptance Criteria

- [ ] Planning artifacts define the MVP as an admin-only Orbit launcher/status/dashboard surface.
- [ ] Hermes can be started or stopped locally through Orbit without modifying production infrastructure.
- [ ] Orbit exposes a Hermes entry only to admins and rejects non-admin API access.
- [ ] The Hermes entry reports useful local status or failure guidance when Hermes is not installed, not configured, stopped, or unreachable.
- [ ] Local verification covers backend compile/tests and a manual or scripted Hermes connectivity check.
- [ ] Final local result is reported to the user with no push or deployment performed.

## Out of Scope

- Production deployment, remote server configuration, git push, and pull request creation until separately approved.
- Vendoring or forking Hermes Agent source into Orbit.
- Replacing Orbit's authentication system.
- Building a custom LLM provider or model router for Hermes.
- Embedding Hermes chat directly in Orbit.
