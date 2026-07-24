---
description: Send request and response bodies, informational responses, trailers, explicit end-of-stream markers, and stream cancellation.
---

# Complete an HTTP message

The first exchange used a bodyless request and one small response. Real
applications also need request bodies, response bodies split across frames,
trailers, informational responses, and cancellation. This tutorial follows
those states on two streams.

## Run the complete lesson

Create `message_lifecycle.py` with this program:

<!-- fmt:off -->
```python
--8<-- "message_lifecycle.py"
```
<!-- fmt:on -->

Run it:

```console
uv run python message_lifecycle.py
```

Expected output:

```text
server received b'hello world' with digest sha-256=:demo:
client received informational 103
client received final 200
client received b'stored' with result accepted
client observed CANCEL on stream 3
```

## Keep each sending direction explicit

Requests and responses each have their own sending direction. Choose one way to
end that direction:

| Last thing to send | API |
| --- | --- |
| headers, with no body or trailers | `send_request(..., end_stream=True)` or `send_response(..., end_stream=True)` |
| a final body chunk | `send_data(..., end_stream=True)` |
| trailers | `send_trailers()` |
| no more bytes after earlier body chunks | `end_stream()` |

Do not set `end_stream=True` when trailers will follow. Once a direction has
ended, another body chunk or trailer block is a stream error.

On receive, `RequestReceived.end_stream`, `ResponseReceived.end_stream`, and
`DataReceived.end_stream` describe the frame that ended the peer's direction.
Use `StreamClosed` to release all state only after both directions have closed
or the stream has been reset.

## Treat body events as chunks

`DataReceived` represents one DATA frame, not an entire HTTP body. Append,
stream, or forward each `event.data` using `event.stream_id`. The example joins
the chunks only because the payload is small.

With manual receive-window updates, call
`acknowledge_received_data(len(event.data), event.stream_id)` only after the
downstream consumer has accepted that chunk.

## Distinguish informational and final responses

A server may call `send_informational_response()` zero or more times before
`send_response()`. The client receives an `InformationalResponseReceived` for
each `1xx` block and one `ResponseReceived` for the final response.

Informational responses do not complete a request. Applications commonly
forward them to the request owner and continue waiting for the final response.

## Handle trailers separately

`TrailersReceived` contains the trailing fields for one stream. Trailers are
metadata after the body; they are not another final response. Preserve them
when the application uses fields such as checksums or final status metadata,
then still wait for `StreamClosed` before discarding stream state.

## Cancel one stream without losing the connection

`reset_stream(stream_id, ErrorCode.CANCEL)` queues RST_STREAM. The peer receives
`StreamReset`, followed by `StreamClosed`; unrelated streams remain usable.

Reset is appropriate when the application no longer needs a body or cannot
continue one exchange. A connection-wide protocol failure is different and
requires closing the transport.

## Keep sensitive fields out of the HPACK dynamic table

Ordinary headers are `(name, value)` byte pairs. Wrap a sensitive field in
`NeverIndexedHeader` when its value must not enter the HPACK dynamic table:

```python
headers = [
    (b":method", b"GET"),
    (b":scheme", b"https"),
    (b":authority", b"example.test"),
    (b":path", b"/private"),
    ngh2.NeverIndexedHeader(b"authorization", b"Bearer secret"),
]
```

Never-indexed encoding controls compression state; it is not encryption.
Transport confidentiality still belongs to TLS.

[Drive a real transport →](../guides/transport.md)
