---
description: Run a complete in-memory HTTP/2 client and server exchange with ngh2.
---

# Run your first HTTP/2 exchange

By the end of this tutorial, you will have sent one request and received one
response across a complete HTTP/2 connection. The client and server run in the
same process so you can see the protocol cycle before sockets, TLS, and async
code are added.

## Create a small project

Create an empty project with CPython 3.10 or newer and install ngh2:

```console
uv init --bare ngh2-tour
cd ngh2-tour
uv add ngh2
```

## Run the complete exchange

Create `first_round_trip.py` with the program below:

<!-- fmt:off -->
```python
--8<-- "first_round_trip.py"
```
<!-- fmt:on -->

Run it:

```console
uv run python first_round_trip.py
```

Expected output:

```text
server received GET /hello on stream 1
client received 200 with b'Hello over HTTP/2\n'
```

The exact same `Connection` API drives both sides. The small `transfer()`
function stands in for a network transport by moving every currently available
byte from one connection to the other.

## Follow one exchange

The program has four protocol steps:

1. Both roles call `initiate_connection()` and exchange their queued preface,
   SETTINGS, and acknowledgements.
2. The client queues a request and `data_to_send()` returns the bytes that can
   cross the transport.
3. The server passes those bytes to `receive_data()` and drains a
   `RequestReceived` event.
4. The server queues response headers and DATA; the client receives the bytes
   and drains `ResponseReceived` and `DataReceived` events.

The request uses stream ID `1`, the first client-initiated stream. The response
uses that same ID so the client can associate it with the request.

## Keep the driver cycle intact

Every transport adapter repeats the same cycle:

1. Read bytes from the transport and pass them to `receive_data()`.
2. Drain `events()` and let the application react.
3. Drain `data_to_send()` and write those bytes to the transport.

Both `receive_data()` and `data_to_send()` can produce events or queue more
protocol work. Draining events and outbound bytes after each protocol action
keeps acknowledgements, flow-control updates, and application messages moving.

The application still chooses when and where I/O happens. Replacing
`transfer()` with a socket, an async stream, or an in-memory test channel does
not change the HTTP/2 connection API.

## What comes next

This first exchange intentionally avoids four concerns:

- multiple concurrent streams;
- request bodies, trailers, and cancellation;
- TLS and ALPN negotiation; and
- manual backpressure and shutdown policy.

Before adding them, connect the objects you just used to HTTP/2's connection,
stream, message, and frame model.

[Understand the protocol model →](protocol-model.md)
