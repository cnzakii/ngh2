---
description: Bound HTTP/2 body buffering with ngh2 receive acknowledgements, send queues, and transport backpressure.
---

# Manage flow control and backpressure

HTTP/2 flow control prevents a sender from putting unlimited DATA on the wire.
It does not automatically bound every buffer in your application. Treat these
three mechanisms separately:

| Layer | What it limits | Signal to watch |
| --- | --- | --- |
| HTTP/2 receive flow control | DATA the peer may send | consumption acknowledged with `acknowledge_received_data()` |
| ngh2 outbound body queue | body bytes submitted but not yet framed | `pending_data()` |
| transport backpressure | framed bytes waiting for the socket | your runtime's `drain()`, writable callback, or equivalent |

## Use automatic receive updates by default

`Configuration(auto_window_update=True)` is the default. ngh2 updates the
receive windows as data is processed, which is appropriate when the application
consumes body events promptly and has its own bounded queues.

Disable automatic updates when downstream consumption must directly control
how much more body data the peer can send.

## Release window only after consumption

Run this complete manual-flow-control example:

<!-- fmt:off -->
```python
--8<-- "manual_flow_control.py"
```
<!-- fmt:on -->

Expected output:

```text
application consumed 65,535 bytes; 4,465 remain queued
application consumed 70,000 bytes; 0 remain queued
upload complete: 70,000 bytes
```

The server is configured with `auto_window_update=False`. For each
`DataReceived` event it waits until the application has consumed the payload,
then releases exactly `len(event.data)` bytes:

```python
server.acknowledge_received_data(len(event.data), event.stream_id)
```

Frame padding is accounted for internally. Do not add it to the acknowledged
amount, and do not acknowledge the same payload twice.

## Bound outbound submission too

`send_data()` retains body bytes until ngh2 can serialize them. A connection or
stream window can therefore leave data queued:

```python
connection.send_data(stream_id, chunk)

if connection.pending_data(stream_id) >= HIGH_WATER_MARK:
    pause_body_producer(stream_id)
```

Resume the producer after peer WINDOW_UPDATE frames arrive, the driver calls
`data_to_send()`, and `pending_data()` drops below your chosen low-water mark.
The values are application policy: choose them from the number of concurrent
streams and your memory budget.

Do not read an entire large file into one bytes object merely because
`send_data()` accepts bytes-like input. Submit bounded chunks. ngh2 provides a
queue, not an application memory limit.

## Change advertised receive capacity deliberately

Use `set_local_window_size()` when the endpoint needs a larger or smaller
absolute receive-window target:

```python
# Connection-wide capacity.
connection.set_local_window_size(1_048_576)

# Additional per-stream capacity. Both limits still apply to DATA.
connection.set_local_window_size(262_144, stream_id=stream_id)
```

Increasing a target queues WINDOW_UPDATE as needed. Reducing one can take
effect gradually while already received DATA drains.

This method does not say that application data was consumed. In manual mode,
continue to call `acknowledge_received_data()` only after the downstream
consumer accepts each `DataReceived` payload.

## Keep reading while a sender is blocked

When a remote window reaches zero, `data_to_send()` can leave body bytes
pending. Continue reading and processing the connection: the peer's
WINDOW_UPDATE frame is what allows the body to resume. Control frames and other
streams may also need to make progress.

[Handle events by scope →](events.md)
