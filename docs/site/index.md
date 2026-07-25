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
and runtime you already use.
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

### Messages in, events out

Call methods for requests, responses, bodies, trailers, and connection
controls, then handle the resulting events. ngh2 takes care of frames, HPACK,
flow-control windows, stream state, and protocol validation.

</div>
<div markdown>

### Measured protocol speed

Across the checked public-API workloads, ngh2 delivers roughly 20× the
protocol-layer throughput of [h2](https://h2.readthedocs.io/).

</div>
<div markdown>

### A proven foundation

[libnghttp2](https://nghttp2.org/documentation/) is the actively maintained
HTTP/2 implementation underneath ngh2. Its protocol engine has been developed
alongside HTTP/2 since the specification's early drafts.

</div>
</div>

### Benchmark details

The recorded `pyperf` run compares complete exchanges through the public APIs
of ngh2 and h2 4.4.0. It includes stream state transitions, HPACK, flow-control
accounting, event construction, and frame serialization.

--8<-- "python-benchmark.md"

These are protocol-layer measurements, not end-to-end client or server
benchmarks. They exclude sockets, TLS, event-loop scheduling, and application
work. Results on other systems and workloads will vary.

[Benchmark source ↗](https://github.com/cnzakii/ngh2/blob/main/benchmarks/compare_h2.py) ·
[Raw `pyperf` result ↗](https://github.com/cnzakii/ngh2/blob/main/docs/assets/python-benchmark.json)
