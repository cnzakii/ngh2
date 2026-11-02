import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from ngh2 import Connection, ConnectionClosed, ErrorCode, Role

H2SPEC = shutil.which("h2spec")
SERVER = Path(__file__).parent / "interop" / "h2spec_server.py"

# h2spec cases that fail today, and why. h2spec 2.6.0 was written for RFC 7540,
# and RFC 9113 relaxed some of the rules it checks. The test fails when a case
# outside this table fails or a case in it passes, so the table stays current.
EXPECTED_FAILURES = {
    "http2/5.1/8": "RFC 9113 section 5.1 allows ignoring frames on closed streams",
    "http2/5.1/9": "RFC 9113 section 5.1 allows ignoring frames on closed streams",
    "http2/5.1/11": "RFC 9113 section 5.1 allows ignoring frames on closed streams",
    "http2/5.1/12": "RFC 9113 section 5.1 allows ignoring frames on closed streams",
    "http2/5.1.1/2": "libnghttp2 cannot tell a lower stream ID from a closed one",
    "http2/5.3.1/2": "RFC 9113 removed the stream self-dependency rule",
    "http2/6.3/1": "libnghttp2 v1.70.0 ignores PRIORITY on stream 0",
    "http2/6.9.1/3": "RFC 9113 section 5.4.1 allows a connection error instead",
}
# The adapter may respond before h2spec's follow-up frame arrives, closing the
# stream so that frame is rightly ignored. The in-memory test below checks the
# same frames without that race.
TIMING_DEPENDENT = {"http2/5.1/5", "http2/5.1/6", "http2/6.1/2"}


@pytest.mark.parametrize("follow_up", ["headers", "data"])
def test_frames_after_end_stream_close_with_stream_closed(follow_up: str) -> None:
    client, server = Connection(Role.CLIENT), Connection(Role.SERVER)
    client.initiate_connection()
    server.initiate_connection()
    for _ in range(2):
        server.receive_data(client.data_to_send())
        client.receive_data(server.data_to_send())
    server.events()
    client.send_request(
        [
            (b":method", b"GET"),
            (b":scheme", b"http"),
            (b":authority", b"example.test"),
            (b":path", b"/"),
        ],
        end_stream=True,
    )
    request = client.data_to_send()
    data = b"\x00\x00\x01\x00\x01\x00\x00\x00\x01x"

    server.receive_data(request + (request if follow_up == "headers" else data))
    server.data_to_send()

    closed = [event for event in server.events() if isinstance(event, ConnectionClosed)]
    assert [event.error_code for event in closed] == [ErrorCode.STREAM_CLOSED]


@pytest.mark.h2spec
@pytest.mark.skipif(H2SPEC is None, reason="h2spec executable is not installed")
def test_h2spec_suite(tmp_path: Path) -> None:
    assert H2SPEC is not None
    report = tmp_path / "h2spec.xml"
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
            [H2SPEC, "-h", "127.0.0.1", "-p", port, "-o", "1", "-j", str(report)],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
    finally:
        server.terminate()
        _, server_errors = server.communicate(timeout=5)

    failed = {
        f"{suite.get('package')}/{number}"
        for suite in ET.parse(report).iter("testsuite")
        for number, case in enumerate(suite.iter("testcase"), 1)
        if case.find("failure") is not None or case.find("error") is not None
    }
    assert failed - TIMING_DEPENDENT == set(EXPECTED_FAILURES), (
        result.stdout + server_errors
    )
