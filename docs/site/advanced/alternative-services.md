---
description: Send and receive HTTP/2 ALTSVC and ORIGIN extension frames without confusing advertisements with trust decisions.
---

# Advertise alternative services and origins

ALTSVC and ORIGIN are connection-management inputs:

- ALTSVC advertises another protocol, host, or port for the same origin;
- ORIGIN advertises origins that may use the current authenticated connection.

ngh2 transports these values. Connection selection, caching, proxies, DNS, and
certificate policy remain application responsibilities.

## Run both advertisements

Create `alternative_services.py` with this program:

<!-- fmt:off -->
```python
--8<-- "alternative_services.py"
```
<!-- fmt:on -->

Run it:

```console
uv run python alternative_services.py
```

Expected output:

```text
alternative for https://example.test: h3=":443"; ma=3600
connection origin set: https://example.test, https://cdn.example.test
```

## Choose ALTSVC scope

Servers call `send_alt_svc()` in one of two forms:

```python
# The origin is stated explicitly at connection scope.
server.send_alt_svc(
    b'h3=":443"; ma=3600',
    origin=b"https://example.test",
)

# A nonzero stream associates the advertisement with that stream's origin.
server.send_alt_svc(b'h3=":443"; ma=3600', stream_id=stream_id)
```

Clients receive `AltSvcReceived`. They may ignore it. A client that uses an
alternative must parse freshness and protocol data, preserve the original
origin, and authenticate the alternative service for that original origin.

## Treat ORIGIN as constrained coalescing input

`send_origins()` queues a server ORIGIN frame:

```python
server.send_origins(
    [b"https://example.test", b"https://cdn.example.test"]
)
```

`OriginReceived.origins` supplies the advertised byte origins. The frame does
not replace certificate checks and must not be treated as permission to send
unrelated credentials or bypass proxy policy. ngh2 does not know whether its
transport uses TLS, so the connection owner must ignore `OriginReceived` on
`h2c` and any other unauthenticated transport.

These extension frames are hop-by-hop. An intermediary consumes them according
to its own policy rather than forwarding them unchanged.

[Look up exact signatures and exceptions →](../reference.md)
