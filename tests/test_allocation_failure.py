import subprocess
import sys
from importlib import import_module

import pytest

from ngh2 import Connection, ConnectionStateError, DataReceived, Role


def check_output_allocation_failures(initial_output: int, payload_size: int) -> None:
    testcapi = import_module("_testcapi")
    set_nomemory = testcapi.set_nomemory
    remove_mem_hooks = testcapi.remove_mem_hooks
    memory_error = MemoryError
    payload = b"x" * payload_size
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


def check_input_allocation_failures() -> None:
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
        wire = client.data_to_send()

        receive = server.receive_data
        failed = False
        # Fail one allocation, then restore before assertions or peer calls.
        set_nomemory(allocation, allocation + 1)
        try:
            receive(wire)
        except memory_error:
            failed = True
        finally:
            remove_mem_hooks()

        if failed:
            try:
                server.receive_data(b"")
            except ConnectionStateError:
                invalidated += 1
                continue
            raise AssertionError(allocation)
        successes += 1
        received = [
            event for event in server.events() if isinstance(event, DataReceived)
        ]
        assert b"".join(event.data for event in received) == payload, allocation
        assert received[-1].end_stream, allocation

    assert invalidated > 0
    assert successes > 0


def run_isolated(scenario: str) -> None:
    testcapi = pytest.importorskip("_testcapi")
    if not hasattr(testcapi, "set_nomemory") or not hasattr(
        testcapi, "remove_mem_hooks"
    ):
        pytest.skip("CPython allocation-failure hooks are unavailable")

    # Allocation hooks affect the whole interpreter, including the test runner.
    result = subprocess.run(
        [sys.executable, __file__, scenario],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


# 100 bytes trims a small output; 60,000 bytes spans frames and grows the output.
@pytest.mark.parametrize("payload_size", [100, 10_000, 60_000])
@pytest.mark.parametrize(
    "initial_output", [0, 1], ids=["complete-frame", "partial-frame"]
)
def test_output_allocation_failure_cannot_leave_a_corrupt_connection(
    initial_output: int,
    payload_size: int,
) -> None:
    run_isolated(f"{initial_output}:{payload_size}")


def test_input_allocation_failure_cannot_leave_a_corrupt_connection() -> None:
    run_isolated("input")


if __name__ == "__main__":
    if sys.argv[1] == "input":
        check_input_allocation_failures()
    else:
        initial, size = sys.argv[1].split(":")
        check_output_allocation_failures(int(initial), int(size))
