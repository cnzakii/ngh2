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

Use a `Connection` to submit requests, responses, body data, and HTTP/2
controls, feed it bytes from any transport, then handle the resulting events.
ngh2 takes care of framing, HPACK, flow control, stream state, scheduling, and
protocol validation.

> ngh2 is currently alpha software. Its public API may change before the first
> stable release.

## Why ngh2

- **Messages in, events out.** Call methods for requests, responses, bodies,
  trailers, and connection controls while ngh2 handles HTTP/2 mechanics.
- **Measured protocol speed.** The checked public-API workloads deliver roughly
  18.5–31× the throughput of [h2](https://h2.readthedocs.io/); see the
  [measurements](#performance).
- **A proven foundation.**
  [libnghttp2](https://nghttp2.org/documentation/) provides the actively
  maintained HTTP/2 protocol engine underneath ngh2.

## Get started

Install ngh2:

```console
python -m pip install ngh2
```

Published wheels include the native HTTP/2 engine; no separate system
installation is required. Linux wheels cover both glibc (manylinux) and musl
(musllinux, such as Alpine) distributions.

The [first-exchange tutorial](https://ngh2.readthedocs.io/en/stable/learn/first-exchange/)
runs a complete in-memory client/server exchange and explains its connection
setup, request, response, and events.

## Documentation

- [Learn ngh2](https://ngh2.readthedocs.io/en/stable/learn/first-exchange/)
  through one connected tutorial sequence.
- [Integrate asyncio transports](https://ngh2.readthedocs.io/en/stable/guides/transport/)
  for clients and servers, then add flow control, recovery, and shutdown.
- [Use advanced HTTP/2](https://ngh2.readthedocs.io/en/stable/advanced/)
  features only when your application needs them.
- [Look up the Python API](https://ngh2.readthedocs.io/en/stable/reference/) for
  exact methods, return values, event fields, and exceptions.
- [Browse the runnable examples](https://github.com/cnzakii/ngh2/tree/main/examples)
  without the surrounding tutorial prose.

## Scope

ngh2 maintains one HTTP/2 connection. It does not open sockets, negotiate TLS
or ALPN, choose a concurrency model, pool connections, route requests, retry
failed work, or implement application timeouts.

The public API covers:

- client and server roles, including h2c upgrade;
- requests, informational and final responses, DATA, trailers, and server push;
- SETTINGS, PING, GOAWAY, RST_STREAM, and automatic or manual receive flow
  control; and
- RFC 9218 priority, extended CONNECT, ALTSVC, ORIGIN, and PRIORITY_UPDATE.

Header names and values are bytes. Header inputs accept iterables of field
pairs, including lists, tuples, generators, and `headers.items()`. Field order
and duplicates are preserved, and submitted fields are snapshotted.

Drive each `Connection` from one thread or task at a time and serialize
operations in protocol order. Independent connections can run concurrently.

ngh2 supports GIL-enabled CPython 3.10 through 3.15 and free-threaded CPython
3.14t and 3.15t.

## Performance

The checked `pyperf` run compares complete exchanges through the public APIs of
ngh2 and hyper-h2. It includes stream state transitions, HPACK, flow-control
accounting, event construction, and frame serialization. Connections and HPACK
state are reused across exchanges; the initial handshake is outside the timer.

| Scenario | ngh2 (µs/exchange) | h2 4.4.1 (µs/exchange) | Relative throughput |
| --- | ---: | ---: | ---: |
| Small request/204 round trip | 2.19 | 58.02 | 26.4× |
| Header block · 32 fields | 4.63 | 130.19 | 28.1× |
| Fragmented request · 5 B | 2.55 | 61.96 | 24.3× |
| Request body · 32 KiB | 6.32 | 117.10 | 18.5× |
| Multiplexed batch · 100 streams | 1.53 | 47.33 | 31.0× |

_Environment: ngh2 0.2.2 (531598d) · h2 4.4.1 · CPython 3.12.13 (64-bit) · Apple M4 · macOS-27.0.1-arm64-arm-64bit · 2026-10-20_

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
