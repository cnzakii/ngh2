# Interoperability checks

`test_interop_hyper_h2.py` runs in the normal unit-test suite and drives ngh2
against hyper-h2 in both client and server roles.

The full h2spec 2.6.0 suite is part of the pytest suite when the external
`h2spec` executable is installed. Run it with:

```console
uv run pytest -m h2spec
```

h2spec predates RFC 9113, so `test_interop_h2spec.py` lists each expected
failure with its reason: RFC 9113 relaxed the rule, libnghttp2 made a
deliberate trade-off, or the pinned libnghttp2 has a known defect. The test
fails on any other failure and on any listed case that starts passing. A few
cases depend on whether the adapter responds before h2spec's follow-up frame
arrives; an in-memory test checks the same frames without that race.

To inspect the output directly, start the test-only cleartext adapter in one
terminal; it prints the selected port:

```console
uv run python tests/interop/h2spec_server.py
```

Then run h2spec in another terminal:

```console
h2spec -h 127.0.0.1 -p PORT
```

## Known libnghttp2 defects

`test_upstream.py` records HTTP/2 rules that the pinned libnghttp2 v1.70.0
does not follow. ngh2 does not work around them in the binding; each test is a
strict expected failure, so a dependency update that fixes one requires
removing its marker.

| Rule | libnghttp2 v1.70.0 behavior |
|---|---|
| [RFC 9113 §6.3](https://www.rfc-editor.org/rfc/rfc9113.html#section-6.3) | [Ignores PRIORITY on stream 0](https://github.com/nghttp2/nghttp2/blob/85e300c79fb6dbcfa9c1013215c8710c1c2cd3d2/lib/nghttp2_session.c#L5697-L5724) |
| [RFC 9218 §7.1](https://www.rfc-editor.org/rfc/rfc9218.html#section-7.1) | [Accepts PRIORITY_UPDATE for stream 0](https://github.com/nghttp2/nghttp2/blob/85e300c79fb6dbcfa9c1013215c8710c1c2cd3d2/lib/nghttp2_session.c#L4860-L4925) |
| [RFC 9113 §6.8](https://www.rfc-editor.org/rfc/rfc9113.html#section-6.8) | [Compares a new GOAWAY only with one already sent](https://github.com/nghttp2/nghttp2/blob/85e300c79fb6dbcfa9c1013215c8710c1c2cd3d2/lib/nghttp2_session.c#L7251-L7252), so queued GOAWAY frames can raise `last_stream_id` |
| [RFC 9113 §6.5.2](https://www.rfc-editor.org/rfc/rfc9113.html#section-6.5.2) | Lets a server queue `ENABLE_PUSH=1` |
| [RFC 8441 §3](https://www.rfc-editor.org/rfc/rfc8441.html#section-3) | Lets an endpoint withdraw `ENABLE_CONNECT_PROTOCOL` |
| [RFC 8336 §2.2](https://www.rfc-editor.org/rfc/rfc8336.html#section-2.2) | [Inverts the ORIGIN flag check](https://github.com/nghttp2/nghttp2/blob/85e300c79fb6dbcfa9c1013215c8710c1c2cd3d2/lib/nghttp2_session.c#L5992-L5993) |
| [RFC 9218 §4](https://www.rfc-editor.org/rfc/rfc9218.html#section-4) | [Discards the whole priority field](https://github.com/nghttp2/nghttp2/blob/85e300c79fb6dbcfa9c1013215c8710c1c2cd3d2/lib/nghttp2_http.c#L612-L626) when one parameter is invalid |

The adapter is not package code and provides no reusable network API. It only
turns request events into minimal responses so h2spec can exercise the native
HTTP/2 state machine through ngh2's public receive and send surfaces.
