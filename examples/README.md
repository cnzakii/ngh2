# Python examples

These standalone programs are runnable lessons for ngh2's public API. Comments
inside each file explain the protocol boundary and the reason for important
steps; the linked documentation adds background, expected results, and the next
skill to learn.

They are examples of protocol integration, not miniature client or server
frameworks. Application routing, pools, retries, timeouts, logging, and
transport shutdown policy remain outside ngh2.

## Prepare the repository

From the repository root, install the locked development environment:

```console
uv sync --locked
```

## Follow the learning path

| Order | Example or guide | What you will learn |
| ---: | --- | --- |
| 1 | [`first_round_trip.py`](python/first_round_trip.py) · [tutorial](../docs/site/learn/first-exchange.md) | one complete request and response across an in-memory connection |
| 2 | [Protocol model](../docs/site/learn/protocol-model.md) | how connections, streams, messages, frames, and events fit together |
| 3 | [`multiplexed_round_trip.py`](python/multiplexed_round_trip.py) · [tutorial](../docs/site/learn/multiplexing.md) | route out-of-order responses by stream ID and complete them on `StreamClosed` |
| 4 | [`message_lifecycle.py`](python/message_lifecycle.py) · [tutorial](../docs/site/learn/message-lifecycle.md) | bodies, informational responses, trailers, explicit end-of-stream, and cancellation |
| 5 | [`asyncio_client.py`](python/asyncio_client.py) · [guide](../docs/site/guides/transport.md) | negotiate TLS ALPN and preserve the read-event-write-event driver cycle |
| 6 | [`asyncio_server.py`](python/asyncio_server.py) · [guide](../docs/site/guides/server.md) | accept TLS connections, isolate connection ownership, and respond after each request ends |
| 7 | [`manual_flow_control.py`](python/manual_flow_control.py) · [guide](../docs/site/guides/flow-control.md) | keep outbound body chunks bounded and release receive capacity only after consumption |
| 8 | [Event handling](../docs/site/guides/events.md) | what every event means and the action that normally follows it |
| 9 | [`graceful_shutdown.py`](python/graceful_shutdown.py) · [guide](../docs/site/guides/errors-and-shutdown.md) | two-stage GOAWAY while an accepted stream finishes |

Continue with advanced features only when the application needs them:

| Example | What you will learn |
| --- | --- |
| [`connection_controls.py`](python/connection_controls.py) | SETTINGS, PING, byte-limited output, connection state, windows, and setting snapshots |
| [`server_push.py`](python/server_push.py) | accepted push, promised stream mapping, and stream-scoped failure when push is disabled |
| [`priorities.py`](python/priorities.py) | RFC 9218 negotiation, PRIORITY_UPDATE, and applied server scheduling state |
| [`h2c_and_connect.py`](python/h2c_and_connect.py) | HTTP/1.1 h2c Upgrade and separately negotiated extended CONNECT |
| [`alternative_services.py`](python/alternative_services.py) | ALTSVC and ORIGIN events without confusing advertisements with trust |

The [Advanced HTTP/2 overview](../docs/site/advanced.md) links each example to
its complete guide.

## Run an example

Run an in-memory lesson directly:

```console
uv run python examples/python/first_round_trip.py
```

Run the network client with its default target or another HTTPS URL:

```console
uv run python examples/python/asyncio_client.py
uv run python examples/python/asyncio_client.py https://example.com/
```

Run the TLS server with a certificate chain and private key:

```console
uv run python examples/python/asyncio_server.py cert.pem key.pem
```

The in-memory examples and the server's request/response path run in the Python
test matrix. Every example is formatted and linted, and the examples directory
is included in static type checking. Live TLS I/O remains an integration check
because remote availability, DNS, certificates, and network policy do not
belong to the package's deterministic test contract.

All examples keep protocol calls in one thread or task. A production adapter
also needs workload-specific body limits, cancellation, logging, timeouts, and
transport shutdown policy.
