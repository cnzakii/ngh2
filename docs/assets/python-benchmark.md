| Scenario | ngh2 (µs/exchange) | h2 4.4.0 (µs/exchange) | Relative throughput |
| --- | ---: | ---: | ---: |
| Small request/204 round trip | 2.56 | 63.20 | 24.7× |
| Header block · 32 fields | 5.76 | 138.43 | 24.0× |
| Fragmented request · 5 B | 2.91 | 65.77 | 22.6× |
| Request body · 32 KiB | 7.63 | 125.26 | 16.4× |
| Multiplexed batch · 100 streams | 1.80 | 49.88 | 27.7× |

_Environment: ngh2 0.1.0 · h2 4.4.0 · CPython 3.12.13 (64-bit) · Apple M4 · macOS-26.5.2-arm64-arm-64bit · 2026-07-25_
