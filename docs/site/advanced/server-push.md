---
description: Send an HTTP/2 push promise, receive a pushed response, reject unwanted push, and handle delayed push failure.
---

# Use server push deliberately

Server push lets a server predict a request and send its response on a new even
stream. It is optional: clients can disable it, reject individual pushes, or
ignore the feature entirely. Use it only when the deployment has evidence that
the prediction helps.

## Run accepted and disabled push paths

Create `server_push.py` with this program:

<!-- fmt:off -->
```python
--8<-- "server_push.py"
```
<!-- fmt:on -->

Run it:

```console
uv run python server_push.py
```

Expected output:

```text
client accepted push 2 for /style.css
pushed response body: b'body {}'
disabled push reported as PushDisabledError
```

## Map the promised stream

`send_push_promise(parent_stream_id, request_headers)` returns the promised
stream ID. Send the pushed response on that returned ID.

The client receives `PushedStreamReceived` with both:

- `stream_id`, the existing request associated with the promise; and
- `promised_stream_id`, the new stream carrying the pushed response.

Create per-stream response state before DATA arrives. If the application does
not want this accepted push, call
`reset_stream(event.promised_stream_id, ErrorCode.CANCEL)`.

## Handle disabled push after serialization

A client disables push with:

```python
client.initiate_connection({ngh2.Setting.ENABLE_PUSH: 0})
```

The server cannot assume a promise will be sent merely because
`send_push_promise()` returned a stream ID. Frame preparation happens later;
`data_to_send()` can produce `FrameNotSent` whose `error` is
`PushDisabledError`.

Treat that outcome as a failed optional operation. Do not fail unrelated
streams, and do not wait for the promised response to become writable.

[Apply RFC 9218 priorities →](priorities.md)
