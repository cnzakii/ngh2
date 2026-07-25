---
description: Negotiate RFC 9218 extensible priority, receive PRIORITY_UPDATE, and apply server scheduling parameters.
---

# Apply RFC 9218 priorities

Priority is advisory input for scheduling concurrent responses. Urgency ranges
from `0` (highest) through `7` (lowest); `incremental=True` says partial
delivery is useful. Correctness must never depend on a particular transmission
order.

## Run a complete priority update

Create `priorities.py` with this program:

<!-- fmt:off -->
```python
--8<-- "priorities.py"
```
<!-- fmt:on -->

Run it:

```console
uv run python priorities.py
```

Expected output:

```text
server received priority update b'u=1, i' for stream 1
server scheduling priority: urgency=1 incremental=True
```

## Negotiate before applying

`NO_RFC7540_PRIORITIES` must be in the first SETTINGS frame and cannot be
changed later. The example enables it on both endpoints:

```python
settings = {ngh2.Setting.NO_RFC7540_PRIORITIES: 1}
client.initiate_connection(settings)
server.initiate_connection(settings)
```

Without the server's setting, `send_priority_update()` returns `False` after
the client knows the feature is disabled. Without the server enabling its local
extensible-priority state, `set_stream_priority()` returns `False`.
Always check these results.

## Turn a signal into scheduling state

The client sends the raw structured-field value:

```python
client.send_priority_update(stream_id, b"u=1, i")
```

The server receives `PriorityUpdateReceived`. ngh2 preserves the raw value; the
application owns parsing and policy. After choosing a `Priority`, the server
can:

- apply it with `set_stream_priority()`;
- inspect it with `get_stream_priority()`; and
- pass `ignore_client_signal=True` when later client updates must not override
  a server policy decision.

Signals are hints. Servers may combine or ignore them, and clients cannot infer
that a requested order was honored.

[Handle h2c and extended CONNECT →](h2c-and-connect.md)
