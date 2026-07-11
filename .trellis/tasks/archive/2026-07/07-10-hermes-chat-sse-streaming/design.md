# Hermes Chat SSE Streaming Design

## Summary

Orbit will replace its buffered Hermes CLI exchange with a POST endpoint that
emits a small, Orbit-owned SSE protocol. A private bridge process runs under
the Hermes Python runtime and turns Hermes's `run_conversation` delta callback
into newline-delimited JSON for Orbit. Orbit validates access and ownership,
translates bridge records into SSE, persists the final or interrupted message,
and never exposes the Hermes dashboard WebSocket/PTY protocol to chat users.

## Boundaries

- Orbit owns browser authentication, authorization, rate/concurrency control,
  persistence, its public SSE contract, cancellation, and all user-visible
  states.
- The Hermes runtime owns model streaming, tools, native conversation state,
  and the native Hermes session id.
- `agents:manage` and `/hermes-dashboard/*` remain unchanged and are never
  part of the chat stream.
- The bridge is a local child process, not a network listener and not an
  Orbit public API. It must run with an explicitly configured Hermes Python
  runtime so it imports the same Hermes installation/configuration used in
  production.

## Runtime Bridge

Add a small Orbit-owned `backend/hermes_stream_bridge.py` that is started by
`HERMES_STREAM_COMMAND`. Its stdin receives one JSON request containing the
prompt and optional native Hermes session id. Its stdout is an NDJSON protocol
with only these record types:

- `started`: native Hermes session id resolved for this turn.
- `delta`: safe assistant text delta.
- `completed`: final assistant content and latest native session id.
- `error`: a safe message and machine-readable error class.

The bridge uses the Hermes runtime's `run_conversation(...,
stream_callback=...)` capability, not `hermes chat -Q -q`, which is explicitly
final-response-only. The bridge must emit records atomically, flush every
delta, send diagnostics only to stderr, and propagate SIGTERM/SIGINT to the
Hermes runtime's interruption mechanism before exiting.

The command is deliberately explicit instead of attempting to infer a Python
interpreter from `HERMES_CHAT_COMMAND`. A deployment can use, for example,
the Python executable inside the Hermes installation's virtual environment.
Orbit returns 503 with deployment guidance when the command is missing or
cannot be started. The current `HERMES_CHAT_COMMAND` buffered path is removed
from the user chat flow rather than being falsely presented as streaming.

## Worker Pool and Reuse

Orbit keeps a fixed private pool of bridge workers instead of starting Python
and importing Hermes for every message. The default pool size is 2 and is
configurable from 1 to 8. Each worker processes one request at a time and keeps
an LRU cache of at most 16 initialized Hermes CLI instances, keyed by Orbit
conversation id. Sticky assignment lets later turns reuse the initialized
Agent and in-memory conversation history while the stored native session id
remains the continuity check and recovery source of truth.

Workers communicate only over their inherited stdin/stdout NDJSON pipes; they
open no new network listener. Normal completion and a handled Hermes error
return the worker to the pool. User cancellation, timeout, unexpected EOF,
malformed protocol, or worker exit discards the whole process group and starts
a replacement. A full pool waits for a bounded configurable interval before
returning 503. This keeps cancellation reliable even though Hermes runs
in-process inside a long-lived worker.

## SSE API

Replace the message-send operation with:

`POST /api/hermes-chat/conversations/{conversation_id}/messages/stream`

Request JSON remains `{ "content": "..." }`. The response has
`Content-Type: text/event-stream`, `Cache-Control: no-cache`, and disables
proxy buffering where applicable. Because browser `EventSource` cannot send a
POST JSON body, the Orbit frontend uses `fetch`, checks the response content
type/status, and parses the SSE byte stream itself.

Events are Orbit-owned JSON payloads:

- `event: started` — generation has been accepted; UI renders the user
  message, a blank assistant placeholder, and generic “正在思考”.
- `event: delta` — `{ "content": "..." }`; append content to the placeholder.
- `event: completed` — `{ "conversation": ..., "message": ... }`; final
  durable assistant message is ready.
- `event: interrupted` — `{ "conversation": ..., "message": ... }`; the
  partial durable message has status `interrupted` and renders “用户终止回答”.
- `event: error` — `{ "status": 502, "detail": "..." }`; no completed
  assistant message is claimed.

The endpoint sends heartbeat comments while Hermes has not yet produced text,
so reverse proxies do not prematurely close a long tool-using turn. It sends a
terminal `completed`, `interrupted`, or `error` event exactly once.

## Persistence and Native Continuity

Add `status VARCHAR(20) NOT NULL DEFAULT 'completed'` to
`hermes_messages`, with allowed assistant values `completed` and
`interrupted`. Existing records remain `completed`; user messages always use
`completed`.

After ownership validation and successful generation-slot acquisition, Orbit
persists the user message before yielding `started`. It accumulates deltas in
memory but writes the assistant message exactly once in `finally`:

- normal bridge completion + non-empty final content → `completed`;
- explicit Stop + non-empty partial content → `interrupted`;
- passive disconnect → transfer the lease and accumulated chunks to a server
  background drain task, then persist the normal completed response;
- timeout/process/bridge failure before useful text → no assistant message.

The conversation title is filled from the first user prompt as before. Store
the bridge's session id as soon as it is known and retain the latest id on
completion/interruption, so the next Orbit turn resumes the corresponding
Hermes native history. The existing conversation/message list endpoints expose
the status for both the user and authorized admin views.

## Cancellation and Concurrency

The UI keeps an `AbortController` while a turn is active and replaces Send
with Stop. Stop first calls the authenticated conversation Stop API, then
aborts the fetch; the server marks that turn as explicitly stopped, discards
the leased worker process group, and persists partial text as `interrupted`.
A passive SSE disconnect has no stop marker, so the response generator hands
the live lease, accumulated chunks, and advisory lock to a tracked server
background task. That task drains Hermes to a terminal record, persists the
final response, then releases or replaces the worker and releases the lock.

`HERMES_CHAT_TIMEOUT=1800` enforces a 30-minute total turn deadline. The
private pipe is read in 15-second intervals so connected clients receive
heartbeat comments and task cancellation remains responsive.

Acquire a cross-worker MySQL advisory lock keyed by Orbit user id before
starting the bridge and hold it for the lifetime of the stream. If it cannot
be acquired immediately, return 409 without starting Hermes. Release it in a
`finally` block on every terminal path. This enforces the agreed one-active-
generation-per-user rule across processes while allowing separate users to
stream independently.

## Frontend Experience

- Optimistically display the user's message and blank assistant card after
  `started`, then append each `delta` safely as plain text.
- Before first delta, show only “正在思考”; never reveal tool activity.
- Render a Stop button during a generation. Existing conversations may be
  viewed while the original stream keeps running in the background, but a
  second send/new/delete action stays disabled until the user slot is free.
- On `completed`, replace the temporary card with the persisted message.
- On `interrupted`, retain partial text and show “用户终止回答”.
- On `error`, remove only the temporary assistant card, retain the user
  message, and show the existing toast/error affordance.
- Conversation detail includes `generating`. After a passive network failure
  or page reload, the frontend restores an empty temporary assistant card,
  shows “正在思考”, and polls the conversation every two seconds. When
  `generating` becomes false, it replaces the temporary card with the durable
  messages returned by the same conversation endpoint.

## Compatibility, Operations, and Rollback

- Permission checks, soft deletion, user isolation, and admin inspection stay
  as in the existing chat feature.
- Existing dashboard proxy and WebSocket tests must remain unchanged.
- Document `HERMES_STREAM_COMMAND`, bridge runtime/version compatibility, and
  the no-buffering requirements for reverse proxies.
- Rollback removes the stream endpoint and bridge configuration/UI. The added
  nullable-safe/defaulted message status remains harmless in MySQL; no
  destructive migration is required.
