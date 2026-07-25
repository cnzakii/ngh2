---
description: Bound body production, release HTTP/2 receive capacity after consumption, and respect transport backpressure.
---

# Manage flow control and backpressure

HTTP/2 flow control limits DATA on the wire. It does not automatically limit
what a body producer gives ngh2 or what a network runtime buffers afterward.
Keep these boundaries separate:

| Boundary | What can build up | Control to use |
| --- | --- | --- |
| body producer → ngh2 | submitted body waiting in ngh2's queue | bounded chunks and `queued_body_size()` |
| HTTP/2 connection | DATA waiting for peer-advertised capacity | keep driving input and output so WINDOW_UPDATE can take effect |
| ngh2 → transport | serialized bytes waiting for the socket | the runtime's `drain()`, writable callback, or equivalent |

## Feed one bounded chunk at a time

The simplest producer policy keeps at most one bounded chunk queued for a
stream:

```python
if connection.queued_body_size(stream_id) == 0:
    chunk = source.read(16_384)
    if chunk:
        connection.send_data(stream_id, chunk)
    else:
        connection.end_stream(stream_id)
```

`queued_body_size(stream_id)` counts body bytes still waiting in ngh2's local
queue. Zero means the HTTP/2 engine has taken the previous chunk, so the
producer can provide another. It does not mean the DATA has reached the socket
or the peer.

The count excludes body already being framed, bytes returned by
`data_to_send()`, transport buffers, HEADERS, control frames, and trailers. It
is a producer watermark, not a sent-byte or process-memory measurement. Keep
each chunk bounded so the data already being framed is bounded too.

Do not use remote-window queries as input admission control. A window is a
shared protocol snapshot, not capacity reserved for the next `send_data()`
call.

## Pipeline with a connection-wide watermark

An adapter serving many active streams may allow a deeper queue while enforcing
one connection-wide memory policy:

```python
if connection.queued_body_size() >= HIGH_WATER_MARK:
    pause_body_producers()

outgoing = connection.data_to_send()
if outgoing:
    transport.write(outgoing)

if connection.queued_body_size() <= LOW_WATER_MARK:
    resume_body_producers()
```

Check the watermark at normal driver points, such as after `data_to_send()`.
There is no need to poll it in a separate loop. Choose the two limits from the
number of concurrent streams and the adapter's memory budget, and continue to
submit bounded chunks.

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

The example submits at most 20,000 body bytes at a time. It briefly holds the
server's WINDOW_UPDATE output so the fourth chunk exhausts the initial stream
window and leaves 4,465 bytes queued. Returning the updates lets the next
`data_to_send()` call take that tail.

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
queued. Continue reading and processing the connection: the peer's
WINDOW_UPDATE frame is what allows the HTTP/2 engine to take more. After
receiving it, drive `data_to_send()` and then reevaluate blocked producers
under the queue policy. Control frames and other streams may also need to make
progress.

[Handle events by scope →](events.md)
