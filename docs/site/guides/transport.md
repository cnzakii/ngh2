---
description: Connect ngh2 to asyncio streams, negotiate HTTP/2 with TLS ALPN, and drive the read-event-write cycle.
---

# Drive an asyncio transport

This guide connects a client-role `Connection` to a real HTTPS server with
Python's standard-library asyncio and TLS support. The result is a small
one-request client; production code can keep the connection open and attach
several request tasks to the same driver.

## Run the client

Create `asyncio_client.py` with this complete program:

<!-- fmt:off -->
```python
--8<-- "asyncio_client.py"
```
<!-- fmt:on -->

Fetch the default URL or supply another HTTPS URL:

```console
uv run python asyncio_client.py
uv run python asyncio_client.py https://example.com/
```

The program prints the numeric status followed by the decoded response body.
It deliberately buffers one body for readability; stream body chunks to their
consumer instead when responses can be large.

## Negotiate HTTP/2 before initializing ngh2

The TLS context advertises only `h2`:

```python
context = ssl.create_default_context()
context.set_alpn_protocols(["h2"])
```

After `asyncio.open_connection()` completes the handshake, check
`selected_alpn_protocol()`. Do not feed TLS application bytes to ngh2 unless
the result is exactly `h2`.

Certificate and hostname verification remain enabled by
`ssl.create_default_context()`. Disabling either would change the security
properties of the client and is not required by ngh2.

## Give one task ownership of the connection

The example keeps all operations in one coroutine:

1. queue the connection preface and request;
2. call `data_to_send()` and handle any events it produces;
3. write the returned bytes and await transport backpressure;
4. read transport bytes and pass them to `receive_data()`;
5. route the resulting events by stream ID; and
6. serialize acknowledgements or control frames, then handle events again.

Both directions can produce events:

```python
connection.receive_data(incoming)
handle_events(connection.events())

outgoing = connection.data_to_send()
handle_events(connection.events())
if outgoing:
    writer.write(outgoing)
    await writer.drain()
```

The event drain after `data_to_send()` catches delayed send failures such as
`FrameNotSent`. Without it, a driver can wait for a response to a frame that
was never serialized.

For a multiplexed client, keep this read-event-write cycle in one connection
driver task. Other tasks can submit work through a queue and receive results
through futures or channels. They should not call the same `Connection`
concurrently.

## Know when the request is finished

`ResponseReceived` carries the final response fields. One or more
`DataReceived` events carry the body. `StreamClosed` is the terminal lifecycle
event, including for responses that end in their headers.

Transport EOF is different: it ends the entire connection. If EOF arrives
before a target stream closes, the response did not complete cleanly.

The application also owns timeouts. A socket read timeout, a request deadline,
and a PING-based liveness policy answer different questions and should not be
hidden inside the protocol object.

[Manage flow control and backpressure →](flow-control.md)
