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

- **Fast.** ngh2 completes HTTP/2 exchanges up to 30× faster than the
  pure-Python [h2](https://h2.readthedocs.io/). See
  [every measured scenario](https://github.com/cnzakii/ngh2#performance).
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

Each scenario runs complete HTTP/2 exchanges through the public APIs of ngh2
and h2, measured with `pyperf`. Times are per iteration: one request, or ten
concurrent requests on one connection, with every response body read. Writes
are separate `send_data()` calls for one request body. Max window raises every
flow-control window to 2³¹−1, the protocol maximum; other scenarios keep the
65,535-byte default. Each library talks to itself in memory and reads its
peer's output in 64 KiB pieces. Work that h2 leaves to its caller, such as
splitting bodies to the window and acknowledging received data, is timed with
it.

<!-- benchmark-table:start -->
| Scenario | ngh2 | h2 4.4.1 | ngh2 speedup |
| --- | ---: | ---: | ---: |
| 1 request · no body | 2.52 µs | 64.42 µs | 25.5× |
| 1 request · 10 B upload | 3.26 µs | 82.56 µs | 25.3× |
| 1 request · 100 KiB upload | 13.46 µs | 246.22 µs | 18.3× |
| 10 concurrent requests · no body | 16.77 µs | 495.19 µs | 29.5× |
| 10 concurrent · 10 MiB upload each · max window | 17.64 ms | 126.28 ms | 7.2× |
| 10 concurrent · 100 writes of 10 KiB upload each | 924.86 µs | 18.75 ms | 20.3× |
| 10 concurrent · 100 writes of 10 KiB upload each · max window | 1.44 ms | 14.44 ms | 10.0× |
| 10 concurrent · 1 MiB download each · max window | 1.40 ms | 13.16 ms | 9.4× |
| 10 concurrent · 10 MiB download each · max window | 17.56 ms | 125.88 ms | 7.2× |

_Environment: ngh2 0.5.0 · h2 4.4.1 · CPython 3.13.12 (64-bit) · Apple M4 · macOS-27.2-arm64-arm-64bit-Mach-O · 2026-11-02_
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
