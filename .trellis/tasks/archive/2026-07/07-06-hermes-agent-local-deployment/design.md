# Hermes Agent Local Deployment Design

## Summary

Add an admin-only Hermes management page to Orbit. Orbit will not embed Hermes internals or proxy chat traffic. It will manage a local Hermes dashboard process through the installed `hermes` CLI and expose the configured dashboard URL.

## Boundaries

- Orbit owns authentication, authorization, UI navigation, and local command invocation.
- Hermes owns agent configuration, API keys, sessions, chat, gateway, and its dashboard UI.
- The integration boundary is the local dashboard URL plus CLI commands:
  - start: `hermes dashboard --host 127.0.0.1 --port 9119 --no-open`
  - stop: `hermes dashboard --stop`
  - status check: HTTP probe of the configured dashboard URL and optional CLI availability.

## Configuration

Add settings in `backend/config.py` and `.env.example`:

- `HERMES_DASHBOARD_URL`, default `http://127.0.0.1:9119`
- `HERMES_DASHBOARD_COMMAND`, default `hermes dashboard --host 127.0.0.1 --port 9119 --no-open`
- `HERMES_DASHBOARD_STOP_COMMAND`, default `hermes dashboard --stop`
- `HERMES_DASHBOARD_TIMEOUT`, default `5`

Commands are split with `shlex.split` and run without a shell.

## Authorization

Add permission `agents:manage` in `backend/auth.py`. Because `admin` receives all permissions and `user` receives an explicit subset, this makes Hermes management admin-only without adding a new role system.

Backend endpoints must call `require_permission(request, "agents:manage")`.

Frontend navigation should show the Hermes entry only when `hasPermission("agents:manage")` is true. `showPage("hermes")` should redirect unauthorized users to the dashboard with a toast, matching the existing admin page behavior.

## API Contract

`GET /api/agents/hermes/status`

Returns:

```json
{
  "configured": true,
  "installed": true,
  "running": false,
  "dashboardUrl": "http://127.0.0.1:9119",
  "message": "Hermes dashboard is not reachable",
  "details": ""
}
```

`POST /api/agents/hermes/start`

Starts the configured command if Hermes is installed and returns the same status shape after a short probe delay.

`POST /api/agents/hermes/stop`

Runs the configured stop command and returns the same status shape after a short probe delay.

Errors:

- `403` when the user lacks `agents:manage`
- `503` when Hermes CLI is not available for start/stop
- `502` or `504` for local dashboard probe failures, represented in status where possible instead of thrown for normal "not running" cases

## Frontend Flow

Add a `hermes` page with:

- status card showing running/stopped/unavailable
- buttons for refresh, start, stop, and open dashboard
- link target from `dashboardUrl`

State lives under `state.hermes` in `public/app.js`. It is loaded when the Hermes page is shown and updated after actions.

## Local Validation

- `npm test`
- direct API status check with an admin session if local MySQL/Redis are available
- Hermes CLI availability check with `command -v hermes`
- if Hermes is installed, run start/status/stop locally; if not installed, verify Orbit reports the missing CLI state cleanly

## Rollback

Revert the added permission, backend endpoints/settings, frontend page/nav/state, `.env.example`, and docs updates. No database migration is needed.
