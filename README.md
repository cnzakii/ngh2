<p align="center">
  <img src="https://github.com/cnzakii/ngh2/raw/refs/heads/main/docs/site/assets/ngh2.svg" width="144" height="144" alt="ngh2 logo">
</p>

<h1 align="center">ngh2</h1>

<p align="center">
  <strong>A fast <a href="https://sans-io.readthedocs.io/">Sans-I/O</a> HTTP/2 library for Python, powered by <a href="https://nghttp2.org/documentation/">libnghttp2</a>.</strong>
</p>

<p align="center">
  <a href="https://github.com/cnzakii/ngh2/actions/workflows/ci.yml"><img src="https://github.com/cnzakii/ngh2/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://codecov.io/gh/cnzakii/ngh2"><img src="https://codecov.io/gh/cnzakii/ngh2/graph/badge.svg?token=NT46X0NDGU" alt="codecov"></a>
  <a href="https://pypi.org/project/ngh2/"><img src="https://img.shields.io/pypi/v/ngh2.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/ngh2/"><img src="https://img.shields.io/pypi/pyversions/ngh2.svg" alt="Python versions"></a>
  <a href="https://github.com/cnzakii/ngh2/blob/main/pyproject.toml"><img src="https://img.shields.io/badge/free--threaded-3.14t-3776AB?logo=python&amp;logoColor=white" alt="Free-threaded CPython 3.14t"></a>
  <a href="https://github.com/cnzakii/ngh2/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
</p>

Use a `Connection` to submit requests, responses, body data, and HTTP/2
controls, feed it bytes from any transport, then handle the resulting events.
ngh2 takes care of framing, HPACK, flow control, stream state, scheduling, and
protocol validation.

> ngh2 is currently alpha software. Its public API may change before the first
> stable release.

## Why ngh2?

- **Messages in, events out.** Call methods for requests, responses, bodies,
  trailers, and connection controls while ngh2 handles HTTP/2 mechanics.
- **Measured protocol speed.** The checked public-API workloads run roughly
  20× faster than [h2](https://h2.readthedocs.io/); see the
  [measurements](#performance).

## Get started

Install ngh2:

```console
python -m pip install ngh2
```

Published wheels include the native HTTP/2 engine; no separate system
installation is required.

The [first-exchange tutorial](https://cnzakii.github.io/ngh2/latest/learn/first-exchange/)
runs a complete in-memory client/server exchange and explains its connection
setup, request, response, and events.

## Documentation

- [Learn ngh2](https://cnzakii.github.io/ngh2/latest/learn/first-exchange/)
  through one connected tutorial sequence.
- [Integrate a transport](https://cnzakii.github.io/ngh2/latest/guides/transport/)
  with TLS, asyncio, flow control, event handling, recovery, and shutdown.
- [Use advanced HTTP/2](https://cnzakii.github.io/ngh2/latest/advanced/)
  features only when your application needs them.
- [Look up the Python API](https://cnzakii.github.io/ngh2/latest/reference/) for
  exact methods, return values, event fields, and exceptions.
- [Browse the runnable examples](examples/README.md) without the surrounding
  tutorial prose.

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

Header names and values are bytes. Drive each `Connection` from one thread or
task at a time and serialize operations in protocol order. Independent
connections can run concurrently.

ngh2 supports GIL-enabled CPython 3.10 through 3.14 and free-threaded CPython
3.14t.

## Performance

The checked `pyperf` run compares complete exchanges through the public APIs of
ngh2 and h2 4.4.0. It includes stream state transitions, HPACK, flow-control
accounting, event construction, and frame serialization.

| Scenario | ngh2 (µs/exchange) | h2 4.4.0 (µs/exchange) | Relative throughput |
| --- | ---: | ---: | ---: |
| Small request/204 round trip | 2.60 | 64.38 | 24.8× |
| Header block · 32 fields | 5.85 | 140.81 | 24.1× |
| Fragmented request · 5 B | 2.93 | 67.73 | 23.1× |
| Request body · 32 KiB | 7.59 | 126.77 | 16.7× |
| Multiplexed batch · 100 streams | 1.78 | 50.91 | 28.5× |

These are protocol-layer measurements, not end-to-end client or server
benchmarks. They exclude sockets, TLS, event-loop scheduling, and application
work. Results on other systems and workloads will vary.

Inspect the [benchmark source][benchmark-script] and
[raw result][benchmark-results].

## Contributing

See [CONTRIBUTING.md][contributing-guide] for development, testing, and release
guidance.

## License

ngh2 is MIT licensed. Distributed wheels also contain libnghttp2 under its MIT
license; both license texts are included in every distribution.

[benchmark-results]: https://github.com/cnzakii/ngh2/blob/main/docs/assets/python-benchmark.json
[benchmark-script]: https://github.com/cnzakii/ngh2/blob/main/benchmarks/compare_h2.py
[contributing-guide]: https://github.com/cnzakii/ngh2/blob/main/CONTRIBUTING.md
