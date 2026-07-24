---
description: Initialize ngh2 after an HTTP/1.1 h2c Upgrade and negotiate an RFC 8441 extended CONNECT stream.
---

# Handle h2c and extended CONNECT

HTTP/1.1 Upgrade and extended CONNECT solve different problems:

- `h2c` Upgrade changes an existing cleartext HTTP/1.1 connection into HTTP/2;
- extended CONNECT creates a protocol tunnel inside an already active HTTP/2
  connection.

Neither feature is needed for an ordinary HTTPS connection negotiated with
TLS ALPN.

## Run both negotiated paths

Create `h2c_and_connect.py` with this program:

<!-- fmt:off -->
```python
--8<-- "h2c_and_connect.py"
```
<!-- fmt:on -->

Run it:

```console
uv run python h2c_and_connect.py
```

Expected output:

```text
binary HTTP2-Settings payload: 00030000000a
client received 204 on upgraded stream 1
server received extended CONNECT for websocket on stream 1
```

## Divide h2c responsibilities correctly

ngh2 does not parse HTTP/1.1. The surrounding application must:

1. create the binary settings payload with `pack_settings_payload()`;
2. apply the HTTP2-Settings header's required base64url encoding;
3. send or validate the HTTP/1.1 Upgrade exchange;
4. decode the received header back to its binary payload; and
5. call `initiate_upgrade()` after the upgrade is accepted.

The client passes the payload it advertised. The server passes the decoded
client payload and can supply its own `local_settings`. The HTTP/1.1 request
becomes HTTP/2 stream `1`, so the application keeps the request metadata it
already parsed and sends the response on stream `1`.

Set `head_request=True` when the upgraded request used `HEAD`; this preserves
the correct response-body semantics.

The Upgrade mechanism is deprecated by RFC 9113. Keep it in compatibility code;
use TLS ALPN for HTTPS or HTTP/2 prior knowledge when the deployment controls
both endpoints.

## Wait for extended CONNECT support

A server advertises:

```python
server.initiate_connection(
    {ngh2.Setting.ENABLE_CONNECT_PROTOCOL: 1}
)
```

The client must receive that setting before sending a request containing
`:protocol`. An extended CONNECT request includes:

```python
[
    (b":method", b"CONNECT"),
    (b":protocol", b"websocket"),
    (b":scheme", b"https"),
    (b":authority", b"example.test"),
    (b":path", b"/chat"),
]
```

After a successful final response, DATA in both directions belongs to the
tunneled protocol. ngh2 still handles HTTP/2 framing and flow control; the
application owns the WebSocket or other tunnel protocol, its shutdown, and its
timeouts.

[Advertise alternative services and origins →](alternative-services.md)
