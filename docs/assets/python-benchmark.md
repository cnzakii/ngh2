| Scenario | ngh2 | h2 4.4.1 | ngh2 speedup |
| --- | ---: | ---: | ---: |
| 1 request · no body | 2.60 µs | 65.61 µs | 25.2× |
| 1 request · 10 B upload | 3.35 µs | 83.46 µs | 24.9× |
| 1 request · 100 KiB upload | 13.51 µs | 249.68 µs | 18.5× |
| 10 concurrent requests · no body | 16.94 µs | 499.58 µs | 29.5× |
| 10 concurrent · 10 MiB upload each · max window | 17.50 ms | 127.74 ms | 7.3× |
| 10 concurrent · 100 writes of 10 KiB upload each | 931.49 µs | 18.77 ms | 20.1× |
| 10 concurrent · 100 writes of 10 KiB upload each · max window | 1.49 ms | 14.48 ms | 9.7× |
| 10 concurrent · 1 MiB download each · max window | 1.44 ms | 13.11 ms | 9.1× |
| 10 concurrent · 10 MiB download each · max window | 17.58 ms | 126.11 ms | 7.2× |

_Environment: ngh2 0.4.0 · h2 4.4.1 · CPython 3.13.12 (64-bit) · Apple M4 · macOS-27.2-arm64-arm-64bit-Mach-O · 2026-11-02_
