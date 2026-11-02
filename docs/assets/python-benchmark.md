| Scenario | ngh2 | h2 4.4.1 | ngh2 speedup |
| --- | ---: | ---: | ---: |
| 1 request · no body | 2.52 µs | 64.42 µs | 25.5× |
| 1 request · 10 B upload | 3.26 µs | 82.56 µs | 25.3× |
| 1 request · 100 KiB upload | 13.46 µs | 246.22 µs | 18.3× |
| 10 concurrent requests · no body | 16.77 µs | 495.19 µs | 29.5× |
| 10 concurrent · 10 MiB upload each · max window | 17.64 ms | 126.28 ms | 7.2× |
| 10 concurrent · 100 writes of 10 KiB upload each | 924.86 µs | 18.75 ms | 20.3× |
| 10 concurrent · 100 writes of 10 KiB upload each · max window | 1.44 ms | 14.44 ms | 10.0× |
| 10 concurrent · 1 MiB download each · max window | 1.40 ms | 13.16 ms | 9.4× |
| 10 concurrent · 10 MiB download each · max window | 17.56 ms | 125.88 ms | 7.2× |

_Environment: ngh2 0.5.0 · h2 4.4.1 · CPython 3.13.12 (64-bit) · Apple M4 · macOS-27.2-arm64-arm-64bit-Mach-O · 2026-11-02_
