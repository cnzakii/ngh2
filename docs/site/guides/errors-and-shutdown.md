---
description: Distinguish immediate exceptions from peer events, choose the right recovery scope, and shut down an ngh2 connection gracefully.
---

# Handle errors and shutdown

Recovery depends on what failed and when, not only on an exception class name.
ngh2 reports rejected calls as Python exceptions. Once a stream operation has
been accepted, its later outcome is part of that stream's event lifecycle.

## Choose recovery by scope

| Situation | What you receive | What remains usable |
| --- | --- | --- |
| an argument or operation is rejected before it is queued | a synchronous exception such as `TypeError`, `ValueError`, or an `NGH2Error` subclass | the method documents the contract; a rejected local call does not automatically mean every stream is lost |
| peer input cannot be processed safely or exceeds a configured resource limit | `ConnectionProtocolError` or `DenialOfServiceError` from `receive_data()` | the connection is failed; close its transport |
| the state machine handles a connection-level protocol error by producing a final GOAWAY | `ConnectionClosed` after output is driven | write the final output, then close the transport |
| one stream cannot accept an operation | `StreamProtocolError` or a stream-specific subclass | other streams and the connection can continue |
| the peer resets one stream | `StreamReset`, followed by `StreamClosed` | other streams and the connection can continue |
| an accepted local stream operation cannot complete later | `StreamClosed.local_error` | fail that stream; unrelated streams normally remain usable |
| a malformed peer message causes a stream error | `StreamClosed` with a nonzero `error_code` | fail that stream and continue driving the connection |
| the peer starts connection shutdown | `GoAwayReceived` | do not create new streams; eligible in-flight streams may continue |

After a fatal receive error, later protocol calls raise `ConnectionStateError`.
Do not reuse that object for a new transport.

## Act on the operation, not only the class

The same exception family can describe rejected local usage or peer input.
Use the method that raised it and the documented scope:

| Exception | Typical meaning | Next action |
| --- | --- | --- |
| `NGH2Error` | base class for ngh2 operational errors | catch only where a shared fallback exists; prefer a specific subclass |
| `ProtocolError` | base class for stream- and connection-level protocol errors | inspect the subclass and the method that raised it |
| `ConnectionStateError` | the operation is too early, too late, or the object already failed | fix local lifecycle ordering; after a fatal receive error, close the transport and discard the object |
| `ConnectionProtocolError` | a connection-scoped peer violation, or a locally rejected role operation | from `receive_data()`, close the failed connection; for a rejected local call, fix the operation |
| `DenialOfServiceError` | peer input exceeded a configured connection resource limit | close the transport; do not replay the bytes into a looser live object |
| `StreamProtocolError` | the operation violates one stream's message state | fail or correct that stream operation; unrelated streams can continue |
| `StreamUnavailableError` | the stream no longer exists or cannot accept the operation | stop work for that stream and release its application state |
| `PushDisabledError` | peer settings invalidated an accepted push promise | skip the promised stream; the parent stream can continue |
| `ConnectionClosingError` | GOAWAY, shutdown, or ID state prevents a new request | submit new work on a replacement connection |
| `NoAvailableStreamIDError` | no local stream identifier remains | drain the connection and create a replacement |
| `InternalError` | the protocol engine encountered an unexpected failure | close the transport and discard the connection |

`TypeError`, `ValueError`, `BufferError`, and `MemoryError`
remain ordinary Python failures documented on the method that can raise them.

## Bound untrusted peer input

Create a `Configuration` before accepting peer bytes. The defaults already
bound decoded header storage, header count, continuation frames, SETTINGS
entries, outstanding acknowledgements, reserved push streams, and suspicious
control-frame rates:

```python
config = ngh2.Configuration(
    max_inbound_header_list_size=32_768,
    max_inbound_header_count=256,
)
connection = ngh2.Connection(ngh2.Role.SERVER, config)
```

Choose smaller or larger limits from the traffic the endpoint is expected to
handle. Exceeding a receive-side resource limit raises
`DenialOfServiceError` and fails the connection; it is not a signal to retry
the same bytes with a looser live object.

## Handle events in the connection driver

Stream handlers should receive response, data, reset, and close events for
their stream ID. The connection driver should keep GOAWAY, connection closure,
SETTINGS, and PING visible even when no request task is currently waiting for
them.

`ErrorCode` represents values carried on the wire in RST_STREAM and GOAWAY. It
does not replace Python exception handling.

To cancel one request without closing the connection:

```python
connection.reset_stream(stream_id, ngh2.ErrorCode.CANCEL)
```

The peer receives `StreamReset`; both endpoints eventually receive
`StreamClosed` and can release that stream's state.

ngh2 also rejects invalid peer HTTP fields instead of silently passing or
discarding them. A malformed request or response does not produce the normal
message event. The state machine queues the appropriate RST_STREAM, and
`StreamClosed.error_code` reports the stream-level protocol failure after
output is driven.

## Stop a server gracefully

Run the two-stage shutdown example:

<!-- fmt:off -->
```python
--8<-- "graceful_shutdown.py"
```
<!-- fmt:on -->

Expected output:

```text
server stopped new streams after GOAWAY 2147483647
client can open another request: False
final GOAWAY covers streams through 1
in-flight stream 1 completed
```

`send_shutdown_notice()` sends the first server GOAWAY with the largest
possible stream ID. This tells the client to stop creating streams without
excluding any stream that was racing with the notice.

In a real server:

1. send the shutdown notice and flush it;
2. wait at least one round-trip time;
3. call `send_goaway()` with the last peer stream that might have been
   processed;
4. let accepted streams finish; and
5. close the caller-owned transport.

`terminate_connection()` is the immediate final path: it queues a final GOAWAY
and stops session processing. Drive output, write the returned bytes, then
handle the resulting `ConnectionClosed` event and close the transport. Use it
for an unrecoverable connection or after your shutdown policy no longer
permits further stream work.

## Retry only requests known to be unprocessed

`GoAwayReceived.last_stream_id` is the highest locally initiated stream the
peer might have processed. Streams with larger IDs are known not to have been
processed and can be retried on a new connection. For lower IDs, retry safety
still depends on whether the request is idempotent and what the application
knows about the response.

This distinction is defined by
[RFC 9113 sections 6.8 and 8.7](https://www.rfc-editor.org/rfc/rfc9113.html#section-6.8);
ngh2 does not choose a retry policy.

[Continue to advanced HTTP/2 controls →](../advanced.md)
