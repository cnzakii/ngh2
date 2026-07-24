import runpy
import sys
from pathlib import Path

import pytest

EXAMPLES = [
    (
        "first_round_trip.py",
        "server received GET /hello on stream 1\n"
        "client received 200 with b'Hello over HTTP/2\\n'\n",
    ),
    (
        "multiplexed_round_trip.py",
        "client opened /slow on stream 1\n"
        "client opened /fast on stream 3\n"
        "client completed /fast: response for /fast\n"
        "client completed /slow: response for /slow\n",
    ),
    (
        "message_lifecycle.py",
        "server received b'hello world' with digest sha-256=:demo:\n"
        "client received informational 103\n"
        "client received final 200\n"
        "client received b'stored' with result accepted\n"
        "client observed CANCEL on stream 3\n",
    ),
    (
        "manual_flow_control.py",
        "application consumed 65,535 bytes; 4,465 remain queued\n"
        "application consumed 70,000 bytes; 0 remain queued\n"
        "upload complete: 70,000 bytes\n",
    ),
    (
        "graceful_shutdown.py",
        "server stopped new streams after GOAWAY 2147483647\n"
        "client can open another request: False\n"
        "final GOAWAY covers streams through 1\n"
        "in-flight stream 1 completed\n",
    ),
    (
        "connection_controls.py",
        "client role=client next_stream=1 read=True write=False\n"
        "connection windows local=65535 remote=65535\n"
        "server received max frame size 32768\n"
        "server received PING b'health01'\n"
        "client settings acknowledged at 32768\n"
        "client received PING acknowledgement b'health01'\n"
        "server effective peer setting 32768\n",
    ),
    (
        "server_push.py",
        "client accepted push 2 for /style.css\n"
        "pushed response body: b'body {}'\n"
        "disabled push reported as PushDisabledError\n",
    ),
    (
        "priorities.py",
        "server received priority update b'u=1, i' for stream 1\n"
        "server scheduling priority: urgency=1 incremental=True\n",
    ),
    (
        "h2c_and_connect.py",
        "binary HTTP2-Settings payload: 00030000000a\n"
        "client received 204 on upgraded stream 1\n"
        "server received extended CONNECT for websocket on stream 1\n",
    ),
    (
        "alternative_services.py",
        'alternative for https://example.test: h3=":443"; ma=3600\n'
        "connection origin set: "
        "https://example.test, https://cdn.example.test\n",
    ),
]


@pytest.mark.parametrize(
    ("filename", "expected_output"),
    EXAMPLES,
    ids=[
        "first-exchange",
        "multiplexing",
        "message-lifecycle",
        "flow-control",
        "graceful-shutdown",
        "connection-controls",
        "server-push",
        "priorities",
        "h2c-and-connect",
        "alternative-services",
    ],
)
def test_python_example_runs(
    filename: str,
    expected_output: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    example = Path(__file__).parents[1] / "examples" / "python" / filename

    runpy.run_path(str(example), run_name="__main__")

    assert capsys.readouterr().out == expected_output


def test_asyncio_example_cli_help(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    example = Path(__file__).parents[1] / "examples" / "python" / "asyncio_client.py"
    monkeypatch.setattr(sys, "argv", [str(example), "--help"])

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(example), run_name="__main__")

    assert exit_info.value.code == 0
    assert "Fetch one HTTPS URL with ngh2" in capsys.readouterr().out
