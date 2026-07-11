# Hermes Agent Local Deployment Implementation Plan

## Checklist

- [x] Load backend/frontend Trellis coding guidelines before editing.
- [x] Add Hermes settings to `backend/config.py` and `.env.example`.
- [x] Add `agents:manage` permission to `backend/auth.py`.
- [x] Add Hermes status/start/stop helpers and `/api/agents/hermes/*` routes in `backend/main.py`.
- [x] Add an admin-only Hermes nav item and page in `public/index.html`.
- [x] Add Hermes state, rendering, actions, and unauthorized page guard in `public/app.js`.
- [x] Add focused styling in `public/styles.css`, reusing the existing card/status/button patterns.
- [x] Update README API/config notes.
- [x] Run `npm test`.
- [x] Run local Hermes checks:
  - `command -v hermes`
  - if installed: start, probe status, stop
  - if not installed: verify the app reports a clean missing-CLI state
- [x] Report local status and ask before deployment or push.

## Validation Commands

```bash
npm test
python3 -m compileall backend run.py tests
command -v hermes || true
```

If a local Hermes install exists:

```bash
hermes dashboard --status
hermes dashboard --host 127.0.0.1 --port 9119 --no-open
curl -sS http://127.0.0.1:9119/api/status
hermes dashboard --stop
```

## Risk Points

- Starting a long-running dashboard process from a web request can orphan output if not detached. Use `subprocess.Popen(..., start_new_session=True)` with stdout/stderr redirected.
- Do not use `shell=True`; commands come from local environment config but should still be split and executed directly.
- Do not expose non-loopback dashboard URLs by default. Hermes docs warn that dashboard exposes API keys and should stay local unless protected.
- Tests may require local MySQL and Redis; if unavailable, report that limitation and still run compile checks.
