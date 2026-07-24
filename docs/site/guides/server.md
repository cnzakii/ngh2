---
description: Accept HTTP/2 over asyncio TLS, give each socket its own ngh2 connection, and respond when a request is complete.
---

# Serve HTTP/2 with asyncio

The client guide connected one `Connection` to an outbound TLS stream. A server
uses the same byte-and-event cycle in the other direction: accept a TLS socket,
create one server-role `Connection` for it, and route each request by stream ID.

This example serves `GET /`, returns `404` for other paths, and returns `405`
for unsupported methods. Routing is deliberately small so the connection
driver stays visible.

## Run the server

Create `asyncio_server.py` with this complete program:

<!-- fmt:off -->
```python
--8<-- "asyncio_server.py"
```
<!-- fmt:on -->

For a local test, create a one-day self-signed certificate:

```console
openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
  -subj "/CN=localhost" -keyout key.pem -out cert.pem
```

Supply a certificate chain and its private key:

```console
uv run python asyncio_server.py cert.pem key.pem
```

The default address is `https://127.0.0.1:8443/`. With a short-lived,
self-signed development certificate, request it from another terminal:

```console
curl --http2 --insecure https://127.0.0.1:8443/
```

The response is:

```text
Hello over HTTP/2
```

`--insecure` is only for a local self-signed certificate. A deployed server
must present a certificate trusted by its clients.

## Negotiate `h2` before accepting protocol bytes

The TLS context advertises HTTP/2 through ALPN:

```python
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(certfile, keyfile)
context.set_alpn_protocols(["h2"])
```

The connection handler checks `selected_alpn_protocol()` before constructing
ngh2 state. If negotiation selected another protocol, those bytes belong to a
different protocol handler and must not be passed to `receive_data()`.

## Give every accepted socket its own connection

`asyncio.start_server()` starts one handler coroutine per accepted transport.
The example constructs one `Connection(Role.SERVER)` inside that handler:

```python
connection = ngh2.Connection(ngh2.Role.SERVER)
connection.initiate_connection()
```

The coroutine is the connection's only owner. It reads bytes, drains events,
queues responses, calls `data_to_send()`, and awaits socket backpressure in
protocol order. Concurrent clients get independent connection objects; streams
on one connection remain multiplexed through its single owner.

## Respond after the request direction ends

`RequestReceived` carries the request headers. A bodyless request is complete
when `event.end_stream` is true. Otherwise the server remembers the headers by
stream ID and waits until:

- `DataReceived.end_stream` is true; or
- `TrailersReceived` supplies the final request fields.

The example does not buffer request bodies because its response does not use
them. An application that consumes a body should process each `DataReceived`
chunk and enforce its own size limit before acknowledging data when manual flow
control is enabled.

`send_response()` receives the same stream ID as the request. A `HEAD` response
ends with its headers; other responses send one DATA chunk:

```python
connection.send_response(stream_id, response_headers)
connection.send_data(stream_id, body, end_stream=True)
```

These calls only queue protocol work. The driver still calls `data_to_send()`,
writes the bytes, awaits `writer.drain()`, and then checks any resulting
events. Keeping output first ensures a terminal `ConnectionClosed` does not
discard final GOAWAY bytes.

## Grow the application outside the driver

A production server still needs application-owned routing, body limits,
timeouts, logging, overload policy, and graceful process shutdown. Keep those
policies around this connection driver rather than adding them to
`Connection`. The [errors and shutdown guide](errors-and-shutdown.md) covers
connection failure and two-stage GOAWAY.

[Manage flow control and backpressure →](flow-control.md)
