| Scenario | ngh2 (µs/exchange) | h2 4.4.1 (µs/exchange) | Relative throughput |
| --- | ---: | ---: | ---: |
| Small request/204 round trip | 2.19 | 58.02 | 26.4× |
| Header block · 32 fields | 4.63 | 130.19 | 28.1× |
| Fragmented request · 5 B | 2.55 | 61.96 | 24.3× |
| Request body · 32 KiB | 6.32 | 117.10 | 18.5× |
| Multiplexed batch · 100 streams | 1.53 | 47.33 | 31.0× |

_Environment: ngh2 0.2.2 (531598d) · h2 4.4.1 · CPython 3.12.13 (64-bit) · Apple M4 · macOS-27.0.1-arm64-arm-64bit · 2026-10-20_
