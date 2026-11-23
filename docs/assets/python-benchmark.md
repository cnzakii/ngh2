| Scenario | ngh2 | h2 4.4.1 | ngh2 speedup |
| --- | ---: | ---: | ---: |
| 1 request · no body | 8.36 µs | 167.62 µs | 20.1× |
| 1 request · 10 B upload | 11.09 µs | 212.02 µs | 19.1× |
| 1 request · 100 KiB upload | 31.30 µs | 607.35 µs | 19.4× |
| 10 concurrent requests · no body | 50.01 µs | 1.47 ms | 29.4× |
| 10 concurrent · 10 MiB upload each · max window | 78.83 ms | 365.40 ms | 4.6× |
| 10 concurrent · 100 writes of 10 KiB upload each | 2.40 ms | 47.97 ms | 20.0× |
| 10 concurrent · 100 writes of 10 KiB upload each · max window | 7.61 ms | 34.42 ms | 4.5× |
| 10 concurrent · 1 MiB download each · max window | 6.42 ms | 29.84 ms | 4.7× |
| 10 concurrent · 10 MiB download each · max window | 73.65 ms | 361.80 ms | 4.9× |

_Environment: ngh2 0.6.0 · h2 4.4.1 · CPython 3.13.12 (64-bit) · Intel(R) Xeon(R) Platinum 8336C CPU @ 2.30GHz · Linux x86_64 · 2026-11-23_
