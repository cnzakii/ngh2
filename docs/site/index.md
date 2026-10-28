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
Build HTTP/2 clients, servers, proxies, and protocol tools on the transport
and runtime you already use. ngh2 turns received bytes into events and your
calls into bytes to send; your code decides how and when those bytes move.
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

### Fast

ngh2 completes HTTP/2 exchanges at least 20× faster than the pure-Python
[h2](https://h2.readthedocs.io/) in every scenario measured below.

</div>
<div markdown>

### Proven protocol engine

Framing, HPACK, flow control, and protocol validation come from
[libnghttp2](https://nghttp2.org/documentation/), the HTTP/2 implementation
behind curl, Node.js, and Apache httpd.

</div>
<div markdown>

### Fits any runtime

ngh2 never opens sockets or starts an event loop, so the same code works with
asyncio, threads, Trio, or in-memory tests.

</div>
</div>

### Benchmark details

Each scenario runs complete exchanges through the public APIs of ngh2 and h2,
measured with `pyperf`. The timer covers stream state, HPACK, flow-control
accounting, event construction, and frame serialization; connections are set
up once outside it.

--8<-- "python-benchmark.md"

These are protocol-layer measurements. They exclude sockets, TLS, event-loop
scheduling, and application work, so end-to-end gains depend on how much of
your program's time HTTP/2 processing takes.

[Benchmark source ↗](https://github.com/cnzakii/ngh2/blob/main/benchmarks/compare_h2.py) ·
[Raw `pyperf` result ↗](https://github.com/cnzakii/ngh2/blob/main/docs/assets/python-benchmark.json) ·
[Reproduce the measurements](contributing.md#performance-measurements)
