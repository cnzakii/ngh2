---
description: Understand every ngh2 event, its scope, and the application action that normally follows it.
---

# Handle events by scope

ngh2 turns protocol input and delayed send outcomes into immutable events.
Drain `events()` after `initiate_upgrade()`, `receive_data()`, and
`data_to_send()`. Route stream events by stream ID and keep connection events
in the task that owns the `Connection`.

## Preserve the driver cycle

```python
connection.receive_data(incoming)
handle_events(connection.events())

outgoing = connection.data_to_send()
handle_events(connection.events())
if outgoing:
    transport.write(outgoing)
```

The second `handle_events()` is required: serialization can produce
`FrameNotSent` or local `StreamClosed` events even when no bytes are returned.

## Stream events

| Event | What it means | Typical application action |
| --- | --- | --- |
| `RequestReceived` | complete request header block | create or find stream state, validate application policy, route the request |
| `ResponseReceived` | complete final response fields | record status and headers; keep waiting until the stream closes |
| `InformationalResponseReceived` | a `1xx` response before the final response | forward or record it without completing the request |
| `TrailersReceived` | trailing fields after the body | attach trailers to the stream result; keep waiting for closure |
| `PushedStreamReceived` | the server reserved `promised_stream_id` for a predicted request | map the promised stream or reject it with `reset_stream(..., CANCEL)` |
| `DataReceived` | one DATA frame payload | deliver or buffer the chunk; acknowledge it after consumption in manual flow-control mode |
| `StreamReset` | the peer ended one stream with RST_STREAM | fail or cancel that stream; leave unrelated streams running |
| `StreamClosed` | both directions ended or the stream was reset | publish the final result and release per-stream state exactly once |

`end_stream` on request, response, and data events describes the peer's sending
direction. `StreamClosed` is the lifecycle event for releasing all stream state.

## Connection events

| Event | What it means | Typical application action |
| --- | --- | --- |
| `SettingsReceived` | the peer supplied new connection settings | update scheduling or feature policy from `remote_settings`; acknowledgement is automatic |
| `SettingsAcknowledged` | the peer acknowledged the oldest local SETTINGS update | treat the corresponding local setting as active and inspect `local_settings` when needed |
| `PingReceived` | the peer sent a liveness probe | no protocol response is needed; ngh2 queues the acknowledgement automatically |
| `PingAcknowledged` | the peer echoed an eight-byte PING payload | match the payload to the caller-owned timer or health check |
| `WindowUpdated` | peer WINDOW_UPDATE increased stream or connection send capacity | drive `data_to_send()` and resume a producer when `pending_data()` falls below policy limits |
| `GoAwayReceived` | the peer began or completed connection shutdown | stop new streams, open a replacement connection, and decide which unprocessed requests are retryable |
| `AltSvcReceived` | raw alternative-service data arrived | parse and cache it only if the client implements Alt-Svc policy and origin authentication |
| `OriginReceived` | the server advertised an origin set | update coalescing policy only after certificate and proxy checks |
| `PriorityUpdateReceived` | a client supplied a raw RFC 9218 field value | parse policy input and optionally apply a `Priority` with `set_stream_priority()` |

Unknown settings remain integer keys in `SettingsReceived.settings`. Ignore
unknown values unless an extension implemented by the application assigns
meaning to them.

## Delayed send failure

`FrameNotSent` means a queued non-DATA frame failed later while
`data_to_send()` prepared output. Inspect:

- `stream_id` to find the affected stream, or zero for a connection frame;
- `frame_type` to identify the operation; and
- `error` to choose stream- or connection-level recovery.

For example, a push promise can be accepted by `send_push_promise()` and later
produce `FrameNotSent(error=PushDisabledError(...))` after the peer disables
push. Do not block waiting for bytes that were never serialized.

[Handle exceptions and shutdown →](errors-and-shutdown.md)
