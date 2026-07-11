# Hermes Chat SSE Streaming

## Goal

Replace the Orbit Hermes chat page's current wait-for-complete response with a
Server-Sent Events (SSE) response flow, so a user sees an assistant reply
arrive incrementally while retaining the existing conversation ownership,
Hermes-session continuity, persistence, and admin/audit boundaries.

## Confirmed Facts

- The existing Hermes Chat task deliberately shipped an MVP non-streaming
  command path; streaming was explicitly out of scope.
- The browser currently calls
  `POST /api/hermes-chat/conversations/{id}/messages` and waits for one JSON
  response before rendering and persisting the assistant message.
- The backend invokes `hermes chat -Q -q` using `subprocess.run`, which
  buffers stdout until the process exits. It derives the native Hermes session
  id from stderr and then persists both messages.
- The existing command contract produces a final reply and session id; the
  repository contains no confirmed token-streaming contract from Hermes.
- The locally installed Hermes Agent is v0.18.0 (2026.7.1). Its documented
  `hermes chat -Q -q` mode intentionally suppresses incremental output and
  prints only the final answer. Its agent runtime does expose a
  `run_conversation(..., stream_callback=...)` callback that receives text
  deltas, but this is an in-process runtime API rather than the current CLI
  command contract.
- This change must not weaken `hermes:chat` user isolation or the existing
  `agents:manage` boundary protecting Hermes service/dashboard control.

## Initial Requirements

- Provide an authenticated, authorized SSE endpoint for sending a message in
  an owned, non-deleted Hermes conversation.
- Render streamed assistant content on the Orbit chat page without exposing
  the Hermes dashboard terminal/WebSocket protocol to normal users.
- Deliver genuine Hermes text deltas: use a dedicated local bridge to the
  Hermes runtime callback rather than pretending a buffered CLI response is
  streaming.
- Make the bridge runtime command explicit and document it for deployment;
  return a clear unavailable error when it is not configured or cannot start.
- Preserve clear errors for unavailable Hermes, process startup failures,
  timeout, malformed/empty upstream output, and interrupted streams.
- Persist a completed assistant message and any returned Hermes session id so
  later turns keep their current behavior.
- Provide a Stop action. An explicit user stop must terminate the active Hermes
  turn and visibly label the current response as “用户终止回答”. A passive
  browser disconnect must continue the turn on the server and persist its
  eventual result.
- Persist the generated partial response after cancellation with an
  `interrupted` completion status, so the same content and label survive a
  page refresh and are visible to authorized administrators.
- Show only a generic “正在思考” state before assistant text begins streaming;
  do not reveal Hermes tool names, arguments, paths, or execution output.
- Permit at most one active Hermes generation per Orbit user, including across
  that user's different conversations. A second request must fail clearly
  until the active turn completes or is stopped.
- Replace the existing buffered chat submit operation; do not leave an
  undocumented non-streaming fallback for normal users.
- Terminate a Hermes turn after 30 minutes; heartbeat waits remain bounded so
  connected clients and recovered background views stay responsive.

## Acceptance Criteria

- [ ] A permitted user receives the assistant reply through a correctly
  formatted SSE response and sees partial content before the request ends.
- [ ] The completed assistant message is persisted once and appears correctly
  after reload; a failed or cancelled stream does not create a misleading
  completed assistant message.
- [ ] A stopped response retains its generated partial content and renders
  “用户终止回答” after the conversation is reloaded.
- [ ] A passive mobile/background disconnect does not stop Hermes; the final
  response is persisted even when the original SSE client is gone.
- [ ] Returning to or refreshing a background-generating conversation shows
  “正在思考” and automatically replaces it with the persisted Hermes result.
- [ ] Subsequent turns retain their stored Hermes session id and existing
  per-user conversation isolation.
- [ ] A second generation request by the same user is rejected while that
  user's existing generation is active; it succeeds after completion or
  cancellation.
- [ ] Unauthorized users and cross-user conversation requests remain rejected
  before any Hermes process is started.
- [ ] Existing Hermes dashboard/agent management authorization remains
  unchanged.
- [ ] Tests cover the SSE event contract, success, upstream failure, timeout,
  cancellation, persistence, and authorization boundaries.

## Likely Out Of Scope

- Replacing the Hermes dashboard terminal/WebSocket bridge.
- Changing the Hermes provider/model configuration or agent-management UI.
- Multi-user shared conversations or resuming partially completed messages.
