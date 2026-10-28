| Scenario | ngh2 (µs/exchange) | h2 4.4.1 (µs/exchange) | Relative throughput |
| --- | ---: | ---: | ---: |
| Small request/204 round trip | 2.01 | 62.36 | 31.0× |
| Header block · 32 fields | 4.33 | 149.18 | 34.5× |
| Fragmented request · 5 B | 2.37 | 68.95 | 29.1× |
| Request body · 32 KiB | 5.92 | 120.97 | 20.4× |
| Multiplexed batch · 100 streams | 1.36 | 48.82 | 36.0× |

_Environment: ngh2 0.3.0 (0383356) · h2 4.4.1 · CPython 3.13.12 (64-bit) · Apple M4 · macOS-27.2-arm64-arm-64bit-Mach-O · 2026-10-28_
