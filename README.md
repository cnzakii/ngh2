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

Build HTTP/2 clients, servers, proxies, and protocol tools with control over
your transport and runtime. Feed incoming bytes to a `Connection`, handle
protocol events, and write the outgoing bytes it produces.

Protocol processing is synchronous. Your application decides when to read,
write, and schedule work; ngh2 manages HTTP/2 connection and stream state.

> ngh2 is currently alpha software. Its public API may change before the first
> stable release.

## Why ngh2

- **Message and event API.** Submit requests, responses, bodies, and trailers;
  handle connection and stream events as Python objects.
- **Measured protocol speed.** The checked public-API workloads deliver roughly
  20–30× the throughput of [h2](https://h2.readthedocs.io/); see the
  [measurements](#performance).
- **Native protocol engine.**
  [libnghttp2](https://nghttp2.org/documentation/) handles framing, HPACK,
  flow control, scheduling, and protocol validation.

## Get started

Install ngh2:

```console
python -m pip install ngh2
```

Supported interpreters are CPython 3.10 through 3.15, including free-threaded
CPython 3.14t and 3.15t.

Wheels bundle libnghttp2 for Linux, macOS, and Windows. Linux wheels support
both glibc (manylinux) and musl (musllinux, including Alpine).

Start with the
[first-exchange tutorial](https://ngh2.readthedocs.io/en/stable/learn/first-exchange/).
It runs a complete client/server exchange in memory and explains how to
initialize connections, send messages, and handle events. The
[example source](https://github.com/cnzakii/ngh2/blob/main/examples/python/first_round_trip.py)
is also available to run directly.

## How it fits

Each `Connection` manages one HTTP/2 connection and its multiplexed streams.
It supports client and server roles, request and response bodies, informational
responses, trailers, flow control, stream cancellation, and connection shutdown.

Your application owns sockets, TLS and ALPN, transport buffering, connection
pooling, routing, retries, and timeouts. The same protocol API can be used with
blocking or asynchronous transports.

Drive each `Connection` from one thread or task at a time. Independent
connections can run concurrently.

## Documentation

- [Tutorials](https://ngh2.readthedocs.io/en/stable/learn/first-exchange/):
  exchange messages, multiplex streams, and manage message lifecycles.
- [Integration guides](https://ngh2.readthedocs.io/en/stable/guides/transport/):
  connect asyncio transports, manage flow control, and handle shutdown.
- [Advanced HTTP/2](https://ngh2.readthedocs.io/en/stable/advanced/):
  configure settings, priority, server push, and protocol extensions.
- [Python API](https://ngh2.readthedocs.io/en/stable/reference/):
  methods, accepted inputs, event fields, and exceptions.
- [Runnable examples](https://github.com/cnzakii/ngh2/tree/main/examples):
  complete programs used throughout the documentation.

## Performance

The checked `pyperf` run compares complete exchanges through the public APIs of
ngh2 and hyper-h2. It includes stream state transitions, HPACK, flow-control
accounting, event construction, and frame serialization. Connections and HPACK
state are reused across exchanges; the initial handshake is outside the timer.

| Scenario | ngh2 (µs/exchange) | h2 4.4.1 (µs/exchange) | Relative throughput |
| --- | ---: | ---: | ---: |
| Small request/204 round trip | 2.19 | 58.13 | 26.5× |
| Header block · 32 fields | 4.67 | 130.51 | 28.0× |
| Fragmented request · 5 B | 2.58 | 61.92 | 24.0× |
| Request body · 32 KiB | 6.27 | 116.71 | 18.6× |
| Multiplexed batch · 100 streams | 1.52 | 47.43 | 31.1× |

_Environment: ngh2 0.3.0 (4a04d5f) · h2 4.4.1 · CPython 3.12.13 (64-bit) · Apple M4 · macOS-27.0.1-arm64-arm-64bit · 2026-10-20_

These are protocol-layer measurements, not end-to-end client or server
benchmarks. They exclude sockets, TLS, event-loop scheduling, and application
work. Results on other systems and workloads will vary.

Inspect the [benchmark source][benchmark-script] and
[raw result][benchmark-results], or follow the
[reproduction steps](CONTRIBUTING.md#performance-measurements).

## Contributing

See [CONTRIBUTING.md][contributing-guide] for development, testing, and release
guidance.

## License

ngh2 is MIT licensed. Distributed wheels also contain libnghttp2 under its MIT
license; both license texts are included in every distribution.

[benchmark-results]: https://github.com/cnzakii/ngh2/blob/main/docs/assets/python-benchmark.json
[benchmark-script]: https://github.com/cnzakii/ngh2/blob/main/benchmarks/compare_h2.py
[contributing-guide]: https://github.com/cnzakii/ngh2/blob/main/CONTRIBUTING.md
