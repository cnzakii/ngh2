---
description: A fast Sans-I/O HTTP/2 library for Python.
---

<div class="home-intro" markdown>
<div markdown>

# ngh2

<p class="home-intro__tagline">
A fast Sans-I/O HTTP/2 library for Python.
</p>

<p class="home-intro__summary">
Build HTTP/2 clients, servers, proxies, and protocol tools around the transport
and runtime you already use. Protocol processing is synchronous; your
application controls when I/O happens.
</p>

[Start the tutorial](learn/first-exchange.md){ .md-button .md-button--primary }
[Read the Python API](reference.md){ .md-button }

</div>

<img class="home-intro__mark" src="assets/ngh2.svg" alt="ngh2">
</div>

!!! warning "Alpha software"

    ngh2 is under active alpha development. Its public API may change before
    the first stable release.

## Why ngh2

<div class="home-reasons" markdown>
<div markdown>

### Message and event API

Submit requests, responses, bodies, and trailers; handle connection and stream
events as Python objects. Each connection can carry multiple concurrent streams.

</div>
<div markdown>

### Measured protocol speed

Across the checked public-API workloads, ngh2 delivers roughly 20–30× the
protocol-layer throughput of [h2](https://h2.readthedocs.io/).

</div>
<div markdown>

### Native protocol engine

[libnghttp2](https://nghttp2.org/documentation/) handles framing, HPACK,
flow control, scheduling, and protocol validation.

</div>
</div>

### Benchmark details

The recorded `pyperf` run compares complete exchanges through the public APIs
of ngh2 and hyper-h2. It includes stream state transitions, HPACK, flow-control
accounting, event construction, and frame serialization. Connections and HPACK
state are reused across exchanges; the initial handshake is outside the timer.

--8<-- "python-benchmark.md"

These are protocol-layer measurements, not end-to-end client or server
benchmarks. They exclude sockets, TLS, event-loop scheduling, and application
work. Results on other systems and workloads will vary.

[Benchmark source ↗](https://github.com/cnzakii/ngh2/blob/main/benchmarks/compare_h2.py) ·
[Raw `pyperf` result ↗](https://github.com/cnzakii/ngh2/blob/main/docs/assets/python-benchmark.json) ·
[Reproduce the measurements](contributing.md#performance-measurements)
