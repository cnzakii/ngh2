# Interoperability checks

`test_interop_hyper_h2.py` runs in the normal unit-test suite and drives ngh2
against hyper-h2 in both client and server roles.

The generic h2spec suite is part of the pytest suite when the external
`h2spec` executable is installed. Run it directly with:

```console
uv run pytest -m h2spec
```

The complete h2spec 2.6.0 suite can also be inspected manually. Start the
test-only cleartext adapter in one terminal; it prints the selected port:

```console
uv run python tests/interop/h2spec_server.py
```

Then run the full suite in another terminal:

```console
h2spec -h 127.0.0.1 -p PORT
```

The full RFC 7540-era suite is diagnostic rather than a passing gate. Its
remaining failures mix protocol behavior in the pinned libnghttp2 release
with transport-close expectations that belong to this test adapter. Inspect
the output from each fresh run instead of treating an older result count as a
compatibility baseline.

The pinned libnghttp2 v1.70.0 ignores a PRIORITY frame on stream zero, although
[RFC 9113 section 6.3](https://www.rfc-editor.org/rfc/rfc9113.html#section-6.3)
still requires a connection error for it. The deprecated frame's payload is
discarded in the
[pinned native receive path](https://github.com/nghttp2/nghttp2/blob/85e300c79fb6dbcfa9c1013215c8710c1c2cd3d2/lib/nghttp2_session.c#L5697-L5724)
without validating that identifier. An in-memory test in
`test_interop_h2spec.py` marks this discrepancy as a strict expected failure,
so a dependency update that fixes it requires removing the marker.

Other full-suite differences need separate analysis: a stream may already be
closed by the adapter's response before an invalid frame arrives, and the
RFC 7540 suite's closed-stream and error-scope expectations can differ from
[RFC 9113 section 5](https://www.rfc-editor.org/rfc/rfc9113.html#section-5).
Compare the same bytes at the same stream state before attributing a failure
to the binding. A full-suite failure count alone does not establish a binding
defect.

The adapter is not package code and provides no reusable network API. It only
turns request events into minimal responses so h2spec can exercise the native
HTTP/2 state machine through ngh2's public receive and send surfaces.
