---
description: Understand every ngh2 event, its scope, and the application action that normally follows it.
---

# Handle events by scope

ngh2 turns protocol progress into immutable events. Drain `events()` after
`initiate_upgrade()`, `receive_data()`, and `data_to_send()`. Route stream
events by stream ID and keep connection events in the task that owns the
`Connection`.

## Preserve the driver cycle

```python
connection.receive_data(incoming)
handle_events(connection.events())

outgoing = connection.data_to_send()
if outgoing:
    transport.write(outgoing)
handle_events(connection.events())
```

Write the returned bytes before handling the second event batch:
`ConnectionClosed` can accompany the connection's final GOAWAY output. That
event batch can also finish a stream or report that a previously accepted
stream operation can no longer complete.

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
| `StreamClosed` | the stream reached its terminal lifecycle state | inspect its result, publish completion or failure, and release per-stream state exactly once |

`end_stream` on request, response, and data events describes the peer's sending
direction. `StreamClosed` is the lifecycle event for releasing all stream state.

Use its fields together:

```python
if isinstance(event, ngh2.StreamClosed):
    if event.local_error is not None:
        fail_stream(event.stream_id, event.local_error)
    elif event.error_code != ngh2.ErrorCode.NO_ERROR:
        fail_stream(event.stream_id, event.error_code)
    else:
        finish_stream(event.stream_id)
```

`local_error` is set only when a previously accepted local stream operation
later fails while output is driven. Otherwise it is `None`. `error_code` is the
HTTP/2 reason used by the stream state machine; zero means ordinary completion.
An explicit peer RST_STREAM is reported first as `StreamReset`, followed by the
terminal `StreamClosed`.

## Connection events

| Event | What it means | Typical application action |
| --- | --- | --- |
| `SettingsReceived` | the peer supplied new connection settings | update scheduling or feature policy from `remote_settings`; acknowledgement is automatic |
| `SettingsAcknowledged` | the peer acknowledged the oldest local SETTINGS update | treat the corresponding local setting as active and inspect `local_settings` when needed |
| `PingReceived` | the peer sent a liveness probe | no protocol response is needed; ngh2 queues the acknowledgement automatically |
| `PingAcknowledged` | the peer echoed an eight-byte PING payload | match the payload to the caller-owned timer or health check |
| `WindowUpdated` | peer WINDOW_UPDATE increased stream or connection send capacity | drive `data_to_send()`, then reevaluate blocked producers under your [body-queue policy](flow-control.md) |
| `GoAwayReceived` | the peer began or completed connection shutdown | stop new streams, open a replacement connection, and decide which unprocessed requests are retryable |
| `ConnectionClosed` | the HTTP/2 state machine needs no more input and has no output left to produce | after writing any bytes returned by the same `data_to_send()` call, close the transport and release connection state |
| `AltSvcReceived` | raw alternative-service data arrived | parse and cache it only if the client implements Alt-Svc policy and origin authentication |
| `OriginReceived` | the server advertised an origin set | ignore it without authenticated TLS; otherwise update coalescing policy only after certificate and proxy checks |
| `PriorityUpdateReceived` | a client supplied a raw RFC 9218 field value | parse policy input and optionally apply a `Priority` with `set_stream_priority()` |

Unknown settings remain integer keys in `SettingsReceived.settings`. Ignore
unknown values unless an extension implemented by the application assigns
meaning to them.

`ConnectionClosed` describes protocol state, not a socket notification. A
transport EOF can arrive first, and a peer GOAWAY can leave accepted streams
active while they finish. The connection owner closes the transport when its
own shutdown policy and stream state allow it.

## Keep one terminal path per stream

Do not build a second completion mechanism around frame output. A successful
`send_*()` call records a valid local operation; `StreamClosed` is the one
terminal event for the stream whether it completes normally, is reset, fails
protocol validation, or encounters a delayed local error.

For example, if peer settings invalidate a queued push promise, its promised
stream closes with `local_error=PushDisabledError(...)`. Fail that optional
push and leave its parent and sibling streams running.

[Handle exceptions and shutdown →](errors-and-shutdown.md)
