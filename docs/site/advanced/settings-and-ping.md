---
description: Update HTTP/2 settings, use PING acknowledgements, inspect connection state, and understand ngh2 query properties.
---

# Control and inspect a connection

SETTINGS changes HTTP/2 behavior for one connection. PING supplies an
eight-byte round-trip signal. Query properties expose current protocol state to
the connection driver; they do not replace transport readiness or application
policy.

## Run the control-frame round trip

Create `connection_controls.py` with this program:

<!-- fmt:off -->
```python
--8<-- "connection_controls.py"
```
<!-- fmt:on -->

Run it:

```console
uv run python connection_controls.py
```

Expected output:

```text
client role=client next_stream=1 read=True write=False
connection windows local=65535 remote=65535
server received max frame size 32768
server received PING b'health01'
client settings acknowledged at 32768
client received PING acknowledgement b'health01'
server effective peer setting 32768
```

## Separate configuration from SETTINGS

`Configuration` controls local binding behavior and resource limits, such as
header storage and automatic receive-window updates. It is fixed when the
`Connection` is created.

HTTP/2 SETTINGS are sent to the peer:

- pass initial settings to `initiate_connection()`;
- call `update_settings()` for a later change;
- read effective peer values from `remote_settings`; and
- after `SettingsAcknowledged`, read acknowledged local values from
  `local_settings`.

`SettingsReceived` and `SettingsAcknowledged` preserve protocol ordering.
Acknowledgement bytes are queued automatically but still need to cross the
caller-owned transport.

## Give PING a caller-owned purpose

`ping()` accepts exactly eight opaque bytes. The peer acknowledgement is
automatic, and `PingAcknowledged` returns the echoed payload.

Use that payload to match a timer or health probe. ngh2 does not own clocks,
timeouts, or the decision to close an unresponsive connection.

## Use query properties for the right decision

| Surface | What it answers | What it does not do |
| --- | --- | --- |
| `role`, `config` | immutable local role and configuration | change a live connection |
| `want_read`, `want_write` | whether protocol processing can still make progress | report socket readability or writability |
| `next_stream_id` | the next locally initiated ID | reserve that ID; use the ID returned by `send_request()` or `send_push_promise()` |
| `can_send_request` | whether a client may currently create a request | guarantee a later call after GOAWAY; still handle `ConnectionClosingError` |
| `pending_data()` | body bytes retained but not yet framed | include bytes already returned to the transport |
| `remote_window_size`, `stream_remote_window_size()` | peer capacity for outbound DATA | replace `pending_data()` or producer watermarks |
| `local_window_size`, `stream_local_window_size()` | remaining inbound DATA capacity | show downstream application queue capacity |
| `local_settings`, `remote_settings` | acknowledged local and effective peer settings | describe application policy |

Stream window queries require a stream still tracked by the state machine and
raise `StreamUnavailableError` after it is no longer available.

## Limit transport-sized output when necessary

`data_to_send(amount)` returns at most `amount` bytes. Repeated calls continue
serializing available protocol output:

```python
while connection.want_write:
    chunk = connection.data_to_send(16_384)
    handle_events(connection.events())
    if not chunk:
        break
    transport.write(chunk)
```

A zero-length result can also mean DATA is blocked by flow control. Keep reading
peer input so WINDOW_UPDATE and other control frames can make progress.

[Use server push →](server-push.md)
