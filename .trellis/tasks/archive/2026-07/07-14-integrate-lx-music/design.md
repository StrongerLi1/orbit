# LX Music Integration Design

## Summary

Run `XCQ0607/lxserver` as an independently built container on loopback port 9527. Expose only its Web player through a second Nginx listener on public port 9528. Nginx reuses the browser's existing host-scoped Orbit cookies in an `auth_request` subrequest to Orbit, strips all credentials, and then proxies the request to LX.

No LX source code is copied into the Orbit application, no Orbit password is shared with LX, and no new SSO token format is introduced.

## Runtime Topology

```text
Browser
  |-- https://shawnstronger.cloud/ -------------> Nginx :443 -> Orbit :3000
  |       Orbit sidebar opens a new tab
  |
  `-- https://shawnstronger.cloud:9528/music ---> Nginx TLS :9528
                                                   |-- auth_request
                                                   |     `-> Orbit /api/auth/me
                                                   |-- 2xx: strip credentials
                                                   |     `-> lxserver 127.0.0.1:9527
                                                   `-- 401: redirect to
                                                         Orbit /?next=music
```

The browser sends host-scoped Orbit cookies to both ports because cookies are not port-scoped. Nginx is the trust boundary: cookies are available only to the internal Orbit auth subrequest and are removed before the LX proxy request.

## Boundaries

Orbit owns:

- login, refresh, logout, ban/delete enforcement, and the user-visible music entry
- the configured public music URL
- the fixed post-login return marker
- the Nginx authentication gate

LX owns:

- music search, playback, player state, cache, and its static Web player
- its own persistent data and logs
- upstream release behavior and music-source compatibility

The gateway exposes the LX Web player and the configured LX management path. Management requires both a valid Orbit browser session and LX's independent `FRONTEND_PASSWORD`; LX client sync and Subsonic remain blocked.

## Orbit Configuration and API

Add one setting:

- `LX_MUSIC_PUBLIC_URL`, default empty. The production value is `https://shawnstronger.cloud:9528/music`.

Add an authenticated integration-discovery endpoint:

```http
GET /api/integrations
```

Response:

```json
{
  "lxMusic": {
    "enabled": true,
    "publicUrl": "https://shawnstronger.cloud:9528/music"
  }
}
```

The endpoint calls `require_user`. An empty configured URL returns `enabled: false` and an empty URL. The endpoint does not reveal secrets or LX internal addresses.

Nginx uses the existing `GET /api/auth/me` endpoint for `auth_request`. That endpoint already validates the access token, reloads the user, and rejects missing, banned, or deleted users. No proxy-specific identity header or alternate authentication endpoint is needed.

## Browser Flow

Add a hidden `音乐` anchor to the existing sidebar:

- show it only after `/api/integrations` returns an enabled LX integration
- set its URL from the API response
- open it with `target="_blank"` and `rel="noopener noreferrer"`

The Nginx unauthorized redirect is fixed to:

```text
https://shawnstronger.cloud/?next=music
```

`next` is a symbolic allowlisted value, not a URL. The frontend captures `next=music` before the existing login-route cleanup. After login, registration, or automatic token refresh it reloads `/api/integrations` and uses `location.replace()` only with the server-configured LX public URL. Unknown `next` values are ignored. This removes the open-redirect and token-in-query risks without a custom callback protocol.

## Nginx Contract

Keep the existing port-80 Orbit server unchanged except for normal configuration maintenance. Add a second server block:

- listen on 9528
- use an `internal` auth location that proxies to `http://127.0.0.1:3000/api/auth/me`
- forward the incoming Cookie only to that internal auth subrequest
- turn 401 into the fixed `/?next=music` Orbit redirect
- proxy the configured LX admin path after Orbit authentication and return 404 for `/rest`
- proxy accepted Web player traffic to `http://127.0.0.1:9527`
- preserve Host, client IP, forwarding scheme, upgrade, and long-response settings
- clear `Cookie`, `Authorization`, `X-User-Token`, and internal identity headers before proxying to LX; forward `X-Frontend-Auth` only for LX's own password-protected management API

The upstream LX management page and APIs require a strong independent admin password as defense in depth. Nginx forwards only LX's `X-Frontend-Auth` header while stripping Orbit cookies and other identity headers. Any future LX upgrade must review its route diff before changing the pinned commit.

## LX Container

Build from a pinned source commit rather than `latest`:

- upstream commit: `0d653bf31b19635dd20299c5b341630b426c79f3`
- upstream version: v1.9.4
- update the production `ws` dependency to at least 8.21.0 during the reproducible build
- verify the installed production dependency tree with `npm audit --omit=dev`

The container publishes only `127.0.0.1:9527:9527`. Nginx is the only public caller.

Runtime settings:

- player path `/music`
- LX player password disabled because the Orbit gate authenticates every public request
- admin path moved to `/_orbit_lx_admin` and protected by both Orbit auth and the LX management password
- Subsonic disabled
- root and path-based LX client sync disabled
- telemetry disabled
- public-user restrictions enabled
- strong admin password supplied from an ignored local environment file
- CPU and memory limits configured

Persist `/server/data` and `/server/logs`. LX stores its cache and downloaded music below `DATA_PATH`, so the data mount also preserves `cache/` and `music/` across container replacement.

## Security Notes

- Orbit and the LX gateway use the same `shawnstronger.cloud` certificate over HTTPS; certificate renewal must be followed by an Nginx reload and a 9528 TLS check.
- Never forward the browser Cookie header to LX. This is the primary credential-isolation invariant.
- Never put Orbit JWTs or passwords in the music URL, query string, LX environment, or LX user database.
- `next=music` is the only accepted return marker.
- LX runs as a separately replaceable dependency and receives no Orbit database or Redis access.
- Music content and custom sources remain subject to their own licenses and platform rules.

## Failure Behavior

- Integration URL missing: hide the sidebar entry; direct port access depends on deployment state.
- Orbit access token expired with a valid refresh token: the music request redirects to Orbit, Orbit refreshes normally, then returns to music.
- Orbit logout, ban, or deletion: `/api/auth/me` fails and the next LX request is not proxied.
- LX unavailable: Nginx returns 502 without changing Orbit availability.
- Music gateway unavailable: Orbit remains usable; the new-tab navigation fails independently.

## Migration and Rollback

Future hostname or gateway-port migration changes `LX_MUSIC_PUBLIC_URL`, the Nginx server name/listener, redirect target, and TLS configuration. Orbit/LX data and API contracts do not change.

Rollback:

1. unset `LX_MUSIC_PUBLIC_URL` to hide the Orbit entry
2. remove or disable the Nginx 9528 server block
3. stop the LX Compose service
4. preserve the LX data directory unless the user explicitly requests deletion

No database migration is required.

## Delivery Split

- Local workspace: implement and test the Orbit configuration, API, sidebar, return flow, Docker recipe, and Nginx source configuration. Do not run a persistent local LX instance.
- Existing server: deploy the pinned LX container, install the 9528 Nginx gateway, open only the gateway port if required, and validate it against the already deployed Orbit auth backend.
- Existing server: deploy only the Orbit LX integration delta after backing up the live files and service definition; do not copy unrelated local workspace changes. Keep repository push deferred.
