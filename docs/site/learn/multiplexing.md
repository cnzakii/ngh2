---
description: Send two independent HTTP/2 requests on one connection and associate events by stream ID.
---

# Multiplex two streams

HTTP/2 lets one connection carry multiple request/response exchanges at the
same time. In this tutorial you will open two streams, let the second response
finish first, and use stream IDs to keep the results separate.

## Run the example

Create `multiplexed_round_trip.py` with this complete program:

<!-- fmt:off -->
```python
--8<-- "multiplexed_round_trip.py"
```
<!-- fmt:on -->

Run it:

```console
uv run python multiplexed_round_trip.py
```

Expected output:

```text
client opened /slow on stream 1
client opened /fast on stream 3
client completed /fast: response for /fast
client completed /slow: response for /slow
```

The client queues both requests before any response is sent. HTTP/2 assigns the
client streams the odd IDs `1` and `3`. The server deliberately sends the
`/fast` response first, demonstrating that completion order does not have to
match request order.

## Keep state by stream ID

Events from all active streams share one connection-level event queue. Use
`event.stream_id` to find the request, response body, cancellation scope, or
application task that owns an event.

```python
bodies: dict[int, bytearray] = {}

for event in connection.events():
    if isinstance(event, ngh2.ResponseReceived):
        bodies[event.stream_id] = bytearray()
    elif isinstance(event, ngh2.DataReceived):
        bodies[event.stream_id].extend(event.data)
    elif isinstance(event, ngh2.StreamClosed):
        if event.local_error is not None:
            raise event.local_error
        if event.error_code != ngh2.ErrorCode.NO_ERROR:
            raise RuntimeError(
                f"stream {event.stream_id} closed with error {event.error_code}"
            )
        completed_body = bytes(bodies.pop(event.stream_id, b""))
        deliver_response(event.stream_id, completed_body)
```

`deliver_response()` represents your client, server, or proxy code. The
important parts are that response state belongs to a stream, not to “the
current request,” and that only a cleanly closed stream publishes a successful
response.

## Separate stream and connection work

Request headers, response headers, body data, trailers, and resets belong to a
stream. SETTINGS, PING, and GOAWAY affect the connection. A real driver normally
routes stream events to per-request state and handles connection events in one
supervising task.

A stream can stall on its flow-control window without preventing control frames
or other sendable streams from progressing. Keep reading from the transport and
keep draining `data_to_send()` even when one body is blocked.

[Complete an HTTP message →](message-lifecycle.md)
