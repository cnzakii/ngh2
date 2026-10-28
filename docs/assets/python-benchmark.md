| Scenario | ngh2 (µs/exchange) | h2 4.4.1 (µs/exchange) | Relative throughput |
| --- | ---: | ---: | ---: |
| Small request/204 round trip | 1.96 | 60.78 | 30.9× |
| Header block · 32 fields | 4.16 | 146.48 | 35.2× |
| Fragmented request · 5 B | 2.34 | 64.37 | 27.5× |
| Request body · 32 KiB | 5.81 | 119.39 | 20.5× |
| Multiplexed batch · 100 streams | 1.32 | 48.32 | 36.7× |

_Environment: ngh2 0.4.0 · h2 4.4.1 · CPython 3.13.12 (64-bit) · Apple M4 · macOS-27.2-arm64-arm-64bit-Mach-O · 2026-10-29_
