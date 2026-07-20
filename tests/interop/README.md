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

The adapter is not package code and provides no reusable network API. It only
turns request events into minimal responses so h2spec can exercise the native
HTTP/2 state machine through ngh2's public receive and send surfaces.
