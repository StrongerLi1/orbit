# Hermes Chat SSE Streaming Implementation Plan

## Steps

- [x] Read backend/frontend specs through `trellis-before-dev` before editing.
- [x] Add `HERMES_STREAM_COMMAND` configuration and deployment documentation;
  keep command parsing shell-free and validate a configured executable.
- [x] Add `backend/hermes_stream_bridge.py` with a flushed NDJSON protocol,
  Hermes runtime setup/resume support, delta callback, completion/error
  records, and signal-driven interruption.
- [x] Extend database initialization and repository mapping for message
  `status`, including a safe additive migration for an existing MySQL table.
- [x] Add backend helpers for bridge process lifecycle, line validation,
  SSE event encoding, heartbeat, timeout, cancellation, and MySQL advisory
  locks keyed by Orbit user id.
- [x] Replace the chat submit endpoint with the authenticated streaming route.
  Validate ownership before lock/process creation; persist the user message,
  title, native session id, and one terminal assistant message according to
  the stream result.
- [x] Update the chat page state/rendering to use `fetch` plus an SSE parser;
  add incremental rendering, generic thinking state, Stop/AbortController,
  interrupted status, and conflict/error recovery.
- [x] Update admin and regular message rendering to display the persisted
  interrupted status without exposing Hermes tool internals.
- [x] Update README, `.env.example`, and API documentation.
- [x] Add focused tests for bridge record parsing, SSE framing and response
  headers, authorization/ownership-before-process, completion persistence,
  timeout/error behavior, cancellation persistence, and advisory-lock 409.
- [x] Replace per-message bridge startup with a fixed sticky worker pool;
  reuse initialized Hermes Agents per Orbit conversation and replace a worker
  after cancellation, timeout, protocol failure, or process exit.
- [x] Allow viewing another existing conversation while a response continues;
  keep stream state bound to its origin conversation so switching views does
  not cancel the request or write messages into the wrong conversation.
- [x] Separate explicit Stop from passive disconnect; drain disconnected turns
  in a tracked server task so mobile backgrounding cannot cancel Hermes or
  lose the final response.
- [x] Enforce a 30-minute turn timeout and expose conversation `generating`
  state so refreshed/disconnected clients show “正在思考” and poll until the
  durable Hermes reply replaces it.
- [x] Run full automated quality checks, real MySQL migration/lock checks, and
  an unauthenticated browser asset smoke test.
- [ ] Run an authenticated live Hermes streaming check in a configured
  environment before deployment.

## Validation

```bash
python3 tests/test_hermes_agent.py
npm test
```

Manual checks with MySQL, Redis, and the configured Hermes runtime:

- A default user sees text appear before the response ends.
- Stop persists partial text with “用户终止回答”, including after refresh.
- A second request from the same user receives 409 while the first runs.
- Another user's stream can proceed independently.
- Cross-user and permission-denied requests start no bridge process.
- The management dashboard remains inaccessible without `agents:manage`.

## Risk Points

- Hermes's streaming callback is a runtime integration rather than the
  final-only CLI contract; pin and document the validated Hermes version.
- A broken NDJSON line must fail safely rather than leak stderr or partial
  internal diagnostics to the browser.
- Streaming responses can be buffered by a reverse proxy; SSE headers and
  production proxy configuration must be verified.
- Process cancellation must kill the whole bridge process group and release
  the advisory lock even when the browser disconnects.
- A native Hermes session can advance during an interrupted turn; retain its
  latest id so Orbit's visible partial transcript and Hermes context agree.

## Rollback Points

- The new bridge and stream endpoint are additive at the routing layer.
- The message `status` column has a default and is backward compatible with
  existing records.
- The original non-streaming command should not remain an undocumented
  fallback; restoring it is an explicit rollback decision.
