# LX Music Integration Implementation Plan

## Checklist

- [x] Load the relevant backend, frontend, cross-layer, and deployment guidance through `trellis-before-dev` before editing product files.
- [x] Add `LX_MUSIC_PUBLIC_URL` to `backend/config.py` and `.env.example`.
- [x] Add authenticated `GET /api/integrations` to `backend/main.py` with the minimal LX enabled/public URL response.
- [x] Add the hidden new-tab `音乐` sidebar anchor to `public/index.html`.
- [x] Extend `public/app.js` to:
  - load integration configuration after authentication
  - show/hide and populate the music entry
  - capture only symbolic `next=music`
  - return to the configured LX URL after login/register/refresh
  - ignore unknown return markers or missing integration config
- [x] Add focused tests for integration enabled/disabled output and frontend return-marker behavior without introducing a new test framework.
- [x] Add `deploy/lxserver/` with:
  - a reproducible Dockerfile pinned to upstream commit `0d653bf31b19635dd20299c5b341630b426c79f3`
  - a production `ws >= 8.21.0` override
  - Compose configuration binding LX only to `127.0.0.1:9527`
  - ignored local secret/config example
  - persistent data/log paths and CPU/memory limits
- [x] Extend `deploy/nginx/orbit.conf` with the 9528 music gateway:
  - internal `/api/auth/me` auth subrequest
  - fixed `/?next=music` redirect
  - Orbit-protected LX management access plus explicit Sync/Subsonic denials for the pinned LX release
  - Web player proxy with long-response/upgrade support
  - mandatory stripping of Orbit cookies and authentication headers
- [x] Update `.gitignore` for LX runtime data and local secrets without ignoring committed examples.
- [x] Update README with topology, setup, security limitations, backup, upgrade, rollback, and copyright notes.
- [x] Run the complete validation matrix and review the final diff against unrelated user changes.
- [x] Read the approved server access notes, inspect current remote Docker/Nginx/firewall state, and create backups before mutation.
- [x] Deploy the pinned LX image and persistent directories on the existing server without running LX persistently on the local machine.
- [x] Install and validate the Nginx 9528 Orbit-auth gateway, opening only port 9528 if the host/cloud firewall requires it.
- [x] Verify remote unauthenticated redirect, authenticated gateway behavior where safely testable, password-protected management access, blocked sync/Subsonic routes, loopback-only 9527, container health, and unchanged Orbit port 80.
- [x] Present local and remote results; do not push or deploy the local Orbit code without separate approval.
- [x] Back up the live Orbit files and service definition, deploy only the LX integration delta, set `LX_MUSIC_PUBLIC_URL`, restart Orbit, and validate sidebar discovery plus login return behavior without pushing code.

Server note: LX, the Nginx gateway, and the Orbit LX integration are installed and pass loopback and public-network tests. Alibaba Cloud TCP 9528 is open; the gateway uses the `shawnstronger.cloud` TLS certificate, anonymous traffic redirects to Orbit over HTTPS, an ephemeral valid Orbit session receives both the enabled integration response and LX player response, the management page requires Orbit plus LX password, Sync/Subsonic routes return 404, raw 9527 remains private, and Orbit port 80/443 is unchanged. The pre-Orbit-deploy rollback is `/opt/orbit/backups/lx-integration-20260714222624`.

## Validation Commands

```bash
npm test
python3 -m compileall backend run.py tests
node --check public/app.js
docker compose -f deploy/lxserver/compose.yaml config
docker build -f deploy/lxserver/Dockerfile -t orbit-lxserver:test deploy/lxserver
docker run --rm orbit-lxserver:test npm audit --omit=dev
docker run --rm -v "$PWD/deploy/nginx/orbit.conf:/etc/nginx/conf.d/orbit.conf:ro" nginx:alpine nginx -t
```

Focused runtime checks when Docker and local Orbit dependencies are available:

```bash
curl -i http://127.0.0.1:3000/api/integrations
curl -i https://shawnstronger.cloud:9528/music
curl -i --cookie '<redacted test cookie>' https://shawnstronger.cloud:9528/music
curl -i http://127.0.0.1:9527/music
```

The persistent local LX runtime checks are skipped by user request. Equivalent container and gateway checks run on the server after backups and configuration validation.

Expected gateway behavior:

- no Orbit Cookie on 9528 -> redirect to `/?next=music`
- valid Orbit Cookie -> LX page response
- Cookie/Authorization absent from LX upstream request evidence
- `/rest` and LX sync routes -> 404; LX admin path -> Orbit auth followed by LX password auth
- stopping LX -> 502 only on 9528; Orbit on port 80 remains healthy

## Risk and Review Points

- `showAuth()` currently normalizes the URL and can discard the query string. Capture the symbolic return marker before that call and test both cold-login and already-authenticated boot paths.
- Cookie headers are sent across ports for the same host. A missing `proxy_set_header Cookie ""` is a release-blocking credential leak.
- Upstream LX routes are absolute and may change. Do not generalize the Orbit port-80 proxy or replace the separate-port boundary with path-based routing.
- Disabling LX player auth is safe only while every public LX path is behind the Orbit Nginx gate and the raw 9527 listener stays loopback-only.
- Do not commit the real LX admin password or runtime data.
- The source build must prove `ws >= 8.21.0`; a green application test alone does not close the known advisory.
- Nginx `auth_request` must be available in the production Nginx build; verify with `nginx -V` or the deployed package before opening 9528.

## Rollback Points

- Frontend/API rollback: unset `LX_MUSIC_PUBLIC_URL`; the nav disappears without touching LX data.
- Gateway rollback: remove the 9528 Nginx server block and reload Nginx.
- Runtime rollback: stop the Compose service; retain the persistent directories.
- Dependency rollback: rebuild the prior pinned image only after confirming it is not vulnerable; never fall back to `latest`.
