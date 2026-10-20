import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ngh2 import Connection, ConnectionClosed, ErrorCode, Role

H2SPEC = shutil.which("h2spec")
SERVER = Path(__file__).parent / "interop" / "h2spec_server.py"


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="libnghttp2 v1.70.0 ignores PRIORITY stream 0; RFC 9113 section 6.3",
)
def test_priority_stream_zero_requires_a_connection_error() -> None:
    """Track the upstream discrepancy without a transport-timing dependency."""
    client, server = Connection(Role.CLIENT), Connection(Role.SERVER)
    client.initiate_connection()
    server.initiate_connection()
    for _ in range(2):
        server.receive_data(client.data_to_send())
        client.receive_data(server.data_to_send())
    server.events()
    priority_on_stream_zero = b"\x00\x00\x05\x02\x00\x00\x00\x00\x00" + bytes(5)

    server.receive_data(priority_on_stream_zero)
    server.data_to_send()

    closed = [event for event in server.events() if isinstance(event, ConnectionClosed)]
    assert len(closed) == 1
    assert closed[0].error_code == ErrorCode.PROTOCOL_ERROR


@pytest.mark.h2spec
@pytest.mark.skipif(H2SPEC is None, reason="h2spec executable is not installed")
def test_generic_h2spec_suite() -> None:
    assert H2SPEC is not None
    server = subprocess.Popen(
        [sys.executable, str(SERVER)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
    )
    assert server.stdout is not None

    try:
        port = server.stdout.readline().strip()
        assert port.isdecimal(), "h2spec adapter did not report its port"
        result = subprocess.run(
            [H2SPEC, "generic", "-h", "127.0.0.1", "-p", port],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    finally:
        server.terminate()
        _, server_errors = server.communicate(timeout=5)

    assert result.returncode == 0, result.stdout + server_errors
