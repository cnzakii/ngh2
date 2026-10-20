| Scenario | ngh2 (µs/exchange) | h2 4.4.1 (µs/exchange) | Relative throughput |
| --- | ---: | ---: | ---: |
| Small request/204 round trip | 2.19 | 58.13 | 26.5× |
| Header block · 32 fields | 4.67 | 130.51 | 28.0× |
| Fragmented request · 5 B | 2.58 | 61.92 | 24.0× |
| Request body · 32 KiB | 6.27 | 116.71 | 18.6× |
| Multiplexed batch · 100 streams | 1.52 | 47.43 | 31.1× |

_Environment: ngh2 0.3.0 (4a04d5f) · h2 4.4.1 · CPython 3.12.13 (64-bit) · Apple M4 · macOS-27.0.1-arm64-arm-64bit · 2026-10-20_
