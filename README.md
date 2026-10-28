<p align="center">
  <img src="https://github.com/cnzakii/ngh2/raw/refs/heads/main/docs/site/assets/ngh2.svg" width="144" height="144" alt="ngh2 logo">
</p>

<h1 align="center">ngh2</h1>

<p align="center">
  <strong>A fast <a href="https://sans-io.readthedocs.io/">Sans-I/O</a> HTTP/2 library for Python, powered by <a href="https://nghttp2.org/documentation/">libnghttp2</a>.</strong>
</p>

<p align="center">
  <a href="https://github.com/cnzakii/ngh2/actions/workflows/ci.yml"><img src="https://github.com/cnzakii/ngh2/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://codecov.io/gh/cnzakii/ngh2"><img src="https://codecov.io/gh/cnzakii/ngh2/graph/badge.svg" alt="codecov"></a>
  <a href="https://pypi.org/project/ngh2/"><img src="https://img.shields.io/pypi/v/ngh2.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/ngh2/"><img src="https://img.shields.io/pypi/pyversions/ngh2.svg" alt="Python versions"></a>
  <a href="https://github.com/cnzakii/ngh2/blob/main/pyproject.toml"><img src="https://img.shields.io/badge/free--threaded-3.14t%20%7C%203.15t-3776AB?logo=python&amp;logoColor=white" alt="Free-threaded CPython 3.14t and 3.15t"></a>
  <a href="https://github.com/cnzakii/ngh2/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
</p>

Build HTTP/2 clients, servers, proxies, and protocol tools on the transport
and runtime you already use. ngh2 turns received bytes into events and your
calls into bytes to send; your code decides how and when those bytes move.

> ngh2 is currently alpha software. Its public API may change before the first
> stable release.

## Why ngh2

- **Fast.** ngh2 completes HTTP/2 exchanges at least 20× faster than the
  pure-Python [h2](https://h2.readthedocs.io/) in every
  [measured scenario](https://github.com/cnzakii/ngh2#performance).
- **Proven protocol engine.** Framing, HPACK, flow control, and protocol
  validation come from [libnghttp2](https://nghttp2.org/documentation/), the
  HTTP/2 implementation behind curl, Node.js, and Apache httpd. CI also runs
  the [h2spec](https://github.com/summerwind/h2spec) conformance suite.
- **Fits any runtime.** ngh2 never opens sockets or starts an event loop, so
  the same code works with asyncio, threads, Trio, or in-memory tests.

## Quick look

A client and a server exchange one request in memory. A real program writes
`data_to_send()` to its socket and passes the bytes it reads to
`receive_data()`.

```python
import ngh2

client = ngh2.Connection(ngh2.Role.CLIENT)
server = ngh2.Connection(ngh2.Role.SERVER)
client.initiate_connection()
server.initiate_connection()

client.send_request(
    [
        (b":method", b"GET"),
        (b":scheme", b"https"),
        (b":authority", b"example.test"),
        (b":path", b"/"),
    ],
    end_stream=True,
)
server.receive_data(client.data_to_send())

for event in server.events():
    if isinstance(event, ngh2.RequestReceived):
        server.send_response(event.stream_id, [(b":status", b"200")])
        server.send_data(event.stream_id, b"hello", end_stream=True)
client.receive_data(server.data_to_send())

for event in client.events():
    print(event)
```

```text
SettingsReceived(settings=mappingproxy({}))
SettingsAcknowledged()
ResponseReceived(stream_id=1, headers=((b':status', b'200'),), end_stream=False)
DataReceived(stream_id=1, data=b'hello', end_stream=True)
StreamClosed(stream_id=1, error_code=<ErrorCode.NO_ERROR: 0>, local_error=None)
```

## Installation

```console
python -m pip install ngh2
```

Or add it to a [uv](https://docs.astral.sh/uv/) project:

```console
uv add ngh2
```

ngh2 supports CPython 3.10 through 3.15, including free-threaded 3.14t and
3.15t. Wheels bundle libnghttp2 for Linux (glibc and musl), macOS, and
Windows, so no system library is needed.

## What ngh2 handles

Each `Connection` manages one HTTP/2 connection and its multiplexed streams,
in the client or server role: request and response bodies, informational
responses, trailers, flow control, stream cancellation, and graceful shutdown.

Your application owns sockets, TLS and ALPN, buffering, connection pooling,
routing, retries, and timeouts. Calls are synchronous and never block on I/O.
Drive each `Connection` from one thread or task at a time; separate
connections can run concurrently.

## Documentation

- [First exchange](https://ngh2.readthedocs.io/en/stable/learn/first-exchange/):
  start here. The tutorials go on to multiplexing and message lifecycles.
- [Integration guides](https://ngh2.readthedocs.io/en/stable/guides/transport/):
  connect asyncio transports, manage flow control, and shut down cleanly.
- [Advanced HTTP/2](https://ngh2.readthedocs.io/en/stable/advanced/):
  settings, priority, server push, and protocol extensions.
- [Python API](https://ngh2.readthedocs.io/en/stable/reference/):
  methods, accepted inputs, event fields, and exceptions.
- [Runnable examples](https://github.com/cnzakii/ngh2/tree/main/examples):
  complete programs used throughout the documentation.

## Performance

Each scenario runs complete exchanges through the public APIs of ngh2 and h2,
measured with `pyperf`. The timer covers stream state, HPACK, flow-control
accounting, event construction, and frame serialization; connections are set
up once outside it.

<!-- benchmark-table:start -->
| Scenario | ngh2 (µs/exchange) | h2 4.4.1 (µs/exchange) | Relative throughput |
| --- | ---: | ---: | ---: |
| Small request/204 round trip | 2.01 | 62.36 | 31.0× |
| Header block · 32 fields | 4.33 | 149.18 | 34.5× |
| Fragmented request · 5 B | 2.37 | 68.95 | 29.1× |
| Request body · 32 KiB | 5.92 | 120.97 | 20.4× |
| Multiplexed batch · 100 streams | 1.36 | 48.82 | 36.0× |

_Environment: ngh2 0.3.0 · h2 4.4.1 · CPython 3.13.12 (64-bit) · Apple M4 · macOS-27.2-arm64-arm-64bit-Mach-O · 2026-10-28_
<!-- benchmark-table:end -->

These are protocol-layer measurements. They exclude sockets, TLS, event-loop
scheduling, and application work, so end-to-end gains depend on how much of
your program's time HTTP/2 processing takes.

Inspect the [benchmark source][benchmark-script] and
[raw result][benchmark-results], or follow the
[reproduction steps](https://github.com/cnzakii/ngh2/blob/main/CONTRIBUTING.md#performance-measurements).

## Contributing

See [CONTRIBUTING.md][contributing-guide] for development, testing, and release
guidance.

## License

ngh2 is MIT licensed. Distributed wheels also contain libnghttp2 under its MIT
license; both license texts are included in every distribution.

[benchmark-results]: https://github.com/cnzakii/ngh2/blob/main/docs/assets/python-benchmark.json
[benchmark-script]: https://github.com/cnzakii/ngh2/blob/main/benchmarks/compare_h2.py
[contributing-guide]: https://github.com/cnzakii/ngh2/blob/main/CONTRIBUTING.md
