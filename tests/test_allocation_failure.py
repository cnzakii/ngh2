import subprocess
import sys
from importlib import import_module

import pytest

from ngh2 import Connection, ConnectionStateError, DataReceived, Role


def check_output_allocation_failures(initial_output: int) -> None:
    testcapi = import_module("_testcapi")
    set_nomemory = testcapi.set_nomemory
    remove_mem_hooks = testcapi.remove_mem_hooks
    memory_error = MemoryError
    payload = b"x" * 10_000
    invalidated = 0
    successes = 0

    for allocation in range(32):
        client, server = Connection(Role.CLIENT), Connection(Role.SERVER)
        client.initiate_connection()
        server.initiate_connection()
        for _ in range(2):
            server.receive_data(client.data_to_send())
            client.receive_data(server.data_to_send())
        client.events()
        server.events()
        stream_id = client.send_request(
            [
                (b":method", b"POST"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/"),
            ]
        )
        server.receive_data(client.data_to_send())
        server.events()
        client.send_data(stream_id, payload, end_stream=True)
        if initial_output:
            server.receive_data(client.data_to_send(initial_output))

        get_output = client.data_to_send
        failed = False
        output = b""
        # Fail one allocation, then restore before assertions or peer calls.
        set_nomemory(allocation, allocation + 1)
        try:
            output = get_output()
        except memory_error:
            failed = True
        finally:
            remove_mem_hooks()

        if failed:
            try:
                output = get_output()
            except ConnectionStateError:
                invalidated += 1
                continue
        else:
            successes += 1
        server.receive_data(output)
        received = [
            event for event in server.events() if isinstance(event, DataReceived)
        ]
        assert b"".join(event.data for event in received) == payload, allocation
        assert received[-1].end_stream, allocation

    assert invalidated > 0
    assert successes > 0


@pytest.mark.parametrize(
    "initial_output", [0, 1], ids=["complete-frame", "partial-frame"]
)
def test_output_allocation_failure_cannot_leave_a_corrupt_connection(
    initial_output: int,
) -> None:
    testcapi = pytest.importorskip("_testcapi")
    if not hasattr(testcapi, "set_nomemory") or not hasattr(
        testcapi, "remove_mem_hooks"
    ):
        pytest.skip("CPython allocation-failure hooks are unavailable")

    # Allocation hooks affect the whole interpreter, including the test runner.
    result = subprocess.run(
        [sys.executable, __file__, str(initial_output)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


if __name__ == "__main__":
    check_output_allocation_failures(int(sys.argv[1]))
