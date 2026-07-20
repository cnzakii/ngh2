<p align="center">
  <img src="https://raw.githubusercontent.com/cnzakii/ngh2/main/docs/assets/ngh2.svg" width="144" height="144" alt="ngh2 logo">
</p>

<h1 align="center">ngh2</h1>

<p align="center">
  <strong>A <a href="https://sans-io.readthedocs.io/">Sans-I/O</a> HTTP/2 protocol library for Python, powered by libnghttp2.</strong>
</p>

<p align="center">
  <a href="https://github.com/cnzakii/ngh2/actions/workflows/ci.yml"><img src="https://github.com/cnzakii/ngh2/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://codecov.io/gh/cnzakii/ngh2"><img src="https://codecov.io/gh/cnzakii/ngh2/graph/badge.svg" alt="codecov"></a>
  <a href="https://pypi.org/project/ngh2/"><img src="https://img.shields.io/pypi/v/ngh2.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/ngh2/"><img src="https://img.shields.io/pypi/pyversions/ngh2.svg" alt="Python versions"></a>
  <a href="https://github.com/cnzakii/ngh2/blob/main/pyproject.toml"><img src="https://img.shields.io/badge/free--threaded-3.14t%20to%203.15t-3776AB?logo=python&amp;logoColor=white" alt="Free-threaded CPython 3.14t–3.15t"></a>
  <a href="https://github.com/cnzakii/ngh2/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
</p>

ngh2 is a [Sans-I/O](https://sans-io.readthedocs.io/) HTTP/2 protocol library
for building clients, servers, proxies, and protocol tools. Feed it bytes from
any transport and drain typed events; queue HTTP/2 operations and pass the
resulting bytes back to the transport.

The Python API is implemented in Cython over
[`libnghttp2`](https://nghttp2.org/documentation/). Wheels include the native
library, so users do not need a system nghttp2 installation.

> ngh2 is currently alpha software. Its public API may change before the first
> stable release.

## Quick Start

Add ngh2 to a uv-managed project:

```console
uv add ngh2
```

Or install it with pip:

```console
pip install ngh2
```

This client-side example queues one request and processes one received chunk.
`transport` represents caller-owned I/O.

```python
import ngh2

connection = ngh2.Connection(ngh2.Role.CLIENT)
connection.initiate_connection()
connection.send_request(
    [
        (b":method", b"GET"),
        (b":scheme", b"https"),
        (b":authority", b"example.com"),
        (b":path", b"/"),
    ],
    end_stream=True,
)
transport.write(connection.data_to_send())

connection.receive_data(transport.read())
transport.write(connection.data_to_send())

for event in connection.events():
    if isinstance(event, ngh2.ResponseReceived):
        print(event.stream_id, event.headers)
    elif isinstance(event, ngh2.DataReceived):
        print(event.data)
```

Outbound methods queue protocol operations. `data_to_send()` serializes what
the current stream state, scheduler, and flow-control windows allow. Body bytes
that cannot yet be serialized remain queued and are reported by
`pending_data()`.

Both `receive_data()` and `data_to_send()` can produce events. Drain `events()`
after either method returns, and pass any bytes from `data_to_send()` to the
transport.

## Scope

ngh2 does not open sockets, negotiate TLS or ALPN, choose a concurrency model,
pool connections, route requests, or implement application timeouts. It
maintains one HTTP/2 connection while higher-level clients, servers, proxies,
and test tools decide how to schedule I/O.

The protocol surface includes:

- client and server roles, including h2c upgrade;
- requests, informational and final responses, DATA, trailers, and server push;
- SETTINGS, PING, GOAWAY, RST_STREAM, and automatic or manual receive flow
  control;
- RFC 9218 extensible priority and the ALTSVC, ORIGIN, and PRIORITY_UPDATE
  extensions supported by libnghttp2.

Header names and values are bytes. Callers supply required pseudo-header
fields in RFC 9113 order. A `Connection` must be driven by one thread or task
at a time, with operations serialized in protocol order; independent
connections can run concurrently. ngh2 supports GIL-enabled CPython 3.10
through 3.15 and free-threaded CPython 3.14t through 3.15t.

## Performance

![Python benchmark comparing ngh2 and h2][benchmark-chart]

The [`pyperf` benchmark][benchmark-script] compares complete exchanges through
the public APIs of ngh2 and h2 4.3.0. It reuses initialized connections and
includes stream state transitions, HPACK, flow control, event construction,
and frame serialization. It excludes socket, TLS, and event-loop costs.

| Scenario | ngh2 (µs/exchange) | h2 4.3.0 (µs/exchange) | Relative throughput |
| --- | ---: | ---: | ---: |
| Small request/204 round trip | 2.58 | 65.15 | 25.3× |
| Header block · 32 fields | 5.92 | 145.05 | 24.5× |
| Fragmented request · 5 B | 2.85 | 67.18 | 23.6× |
| Request body · 32 KiB | 7.55 | 131.48 | 17.4× |
| Multiplexed batch · 100 streams | 1.83 | 52.04 | 28.5× |

These local pyperf results were produced with CPython 3.12.13 on an Apple M4
running macOS 26.5. The multiplexed result is normalized per completed stream.
The [raw pyperf result][benchmark-results] records the samples and environment;
results on other systems will vary.

## Acknowledgements

[`libnghttp2`](https://nghttp2.org/documentation/) provides HTTP/2 framing,
HPACK, stream state, flow control, validation, and outbound scheduling. ngh2
provides the Python object model, typed events, error mapping, buffer lifetimes,
and distribution packaging.

## Contributing

See [CONTRIBUTING.md][contributing-guide] for development, testing, and release
guidance.

## License

ngh2 is MIT licensed. Distributed wheels also contain libnghttp2 under its MIT
license; both license texts are included in every distribution.

[benchmark-chart]: https://raw.githubusercontent.com/cnzakii/ngh2/main/docs/assets/python-benchmark.svg
[benchmark-results]: https://github.com/cnzakii/ngh2/blob/main/docs/assets/python-benchmark.json
[benchmark-script]: https://github.com/cnzakii/ngh2/blob/main/benchmarks/compare_h2.py
[contributing-guide]: https://github.com/cnzakii/ngh2/blob/main/CONTRIBUTING.md
