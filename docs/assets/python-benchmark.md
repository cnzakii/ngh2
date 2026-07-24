| Scenario | ngh2 (µs/exchange) | h2 4.4.0 (µs/exchange) | Relative throughput |
| --- | ---: | ---: | ---: |
| Small request/204 round trip | 2.60 | 64.38 | 24.8× |
| Header block · 32 fields | 5.85 | 140.81 | 24.1× |
| Fragmented request · 5 B | 2.93 | 67.73 | 23.1× |
| Request body · 32 KiB | 7.59 | 126.77 | 16.7× |
| Multiplexed batch · 100 streams | 1.78 | 50.91 | 28.5× |

_Environment: ngh2 0.1.0 · h2 4.4.0 · CPython 3.12.13 (64-bit) · Apple M4 · macOS-26.5.2-arm64-arm-64bit · 2026-07-24_
