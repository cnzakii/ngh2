"""Compare complete HTTP/2 exchanges through the public Python APIs."""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from time import perf_counter

import h2
import pyperf
from h2.config import H2Configuration
from h2.connection import H2Connection
from h2.events import DataReceived as H2DataReceived
from h2.events import RequestReceived as H2RequestReceived
from h2.events import ResponseReceived as H2ResponseReceived

import ngh2

Headers = tuple[tuple[bytes, bytes], ...]

SMALL_REQUEST = (
    (b":method", b"GET"),
    (b":scheme", b"https"),
    (b":authority", b"example.test"),
    (b":path", b"/items"),
    (b"accept", b"application/json"),
)
LARGE_REQUEST = SMALL_REQUEST + tuple(
    (f"x-field-{index:02d}".encode(), f"value-{index:02d}".encode())
    for index in range(27)
)
BODY = b"x" * 16_384
BODY_REQUEST = (
    (b":method", b"POST"),
    (b":scheme", b"https"),
    (b":authority", b"example.test"),
    (b":path", b"/upload"),
    (b"content-length", str(2 * len(BODY)).encode()),
)
RESPONSE = ((b":status", b"204"),)

SCENARIOS = (
    ("small_round_trip", "Small request/204 round trip", SMALL_REQUEST, None, (), 1),
    ("headers_32", "Header block · 32 fields", LARGE_REQUEST, None, (), 1),
    ("fragmented_5b", "Fragmented request · 5 B", SMALL_REQUEST, 5, (), 1),
    ("body_32k", "Request body · 32 KiB", BODY_REQUEST, None, (BODY,) * 2, 1),
    (
        "multiplexed_100",
        "Multiplexed batch · 100 streams",
        SMALL_REQUEST,
        None,
        (),
        100,
    ),
)


class Ngh2RoundTrip:
    """Run one or more completed request/response exchanges with ngh2."""

    __slots__ = (
        "batch_size",
        "body_chunks",
        "client",
        "fragment_size",
        "headers",
        "server",
    )

    def __init__(
        self,
        headers: Headers,
        fragment_size: int | None,
        body_chunks: tuple[bytes, ...],
        batch_size: int,
    ) -> None:
        self.client = ngh2.Connection(ngh2.Role.CLIENT)
        self.server = ngh2.Connection(ngh2.Role.SERVER)
        self.headers = headers
        self.fragment_size = fragment_size
        self.body_chunks = body_chunks
        self.batch_size = batch_size

        self.client.initiate_connection()
        self.server.initiate_connection()
        for source, destination in (
            (self.client, self.server),
            (self.server, self.client),
            (self.client, self.server),
            (self.server, self.client),
        ):
            data = source.data_to_send()
            if data:
                destination.receive_data(data)
        self.client.events()
        self.server.events()

    def __call__(self) -> tuple[int, int, int]:
        stream_ids = []
        for _ in range(self.batch_size):
            stream_id = self.client.send_request(
                self.headers,
                end_stream=not self.body_chunks,
            )
            stream_ids.append(stream_id)
            for index, chunk in enumerate(self.body_chunks):
                self.client.send_data(
                    stream_id,
                    chunk,
                    end_stream=index == len(self.body_chunks) - 1,
                )

        request_wire = self.client.data_to_send()
        request_events = []
        if self.fragment_size is None:
            self.server.receive_data(request_wire)
            request_events.extend(self.server.events())
        else:
            for offset in range(0, len(request_wire), self.fragment_size):
                self.server.receive_data(
                    request_wire[offset : offset + self.fragment_size],
                )
                request_events.extend(self.server.events())

        for stream_id in stream_ids:
            self.server.send_response(stream_id, RESPONSE, end_stream=True)
        response_wire = self.server.data_to_send()
        self.server.events()
        self.client.receive_data(response_wire)
        response_events = self.client.events()

        requests = sum(
            isinstance(event, ngh2.RequestReceived) for event in request_events
        )
        body_bytes = sum(
            len(event.data)
            for event in request_events
            if isinstance(event, ngh2.DataReceived)
        )
        responses = sum(
            isinstance(event, ngh2.ResponseReceived) for event in response_events
        )
        return requests, body_bytes, responses


class H2RoundTrip:
    """Run one or more completed request/response exchanges with hyper-h2."""

    __slots__ = (
        "batch_size",
        "body_chunks",
        "client",
        "fragment_size",
        "headers",
        "server",
    )

    def __init__(
        self,
        headers: Headers,
        fragment_size: int | None,
        body_chunks: tuple[bytes, ...],
        batch_size: int,
    ) -> None:
        self.client = H2Connection(H2Configuration(client_side=True))
        self.server = H2Connection(H2Configuration(client_side=False))
        self.headers = headers
        self.fragment_size = fragment_size
        self.body_chunks = body_chunks
        self.batch_size = batch_size

        self.client.initiate_connection()
        self.server.initiate_connection()
        for source, destination in (
            (self.client, self.server),
            (self.server, self.client),
            (self.client, self.server),
            (self.server, self.client),
        ):
            data = source.data_to_send()
            if data:
                destination.receive_data(data)

    def __call__(self) -> tuple[int, int, int]:
        stream_ids = []
        for _ in range(self.batch_size):
            stream_id = self.client.get_next_available_stream_id()
            self.client.send_headers(
                stream_id,
                self.headers,
                end_stream=not self.body_chunks,
            )
            stream_ids.append(stream_id)
            for index, chunk in enumerate(self.body_chunks):
                self.client.send_data(
                    stream_id,
                    chunk,
                    end_stream=index == len(self.body_chunks) - 1,
                )

        request_wire = self.client.data_to_send()
        request_events = []
        if self.fragment_size is None:
            request_events.extend(self.server.receive_data(request_wire))
        else:
            for offset in range(0, len(request_wire), self.fragment_size):
                request_events.extend(
                    self.server.receive_data(
                        request_wire[offset : offset + self.fragment_size],
                    ),
                )

        for event in request_events:
            if isinstance(event, H2DataReceived):
                self.server.acknowledge_received_data(
                    event.flow_controlled_length,
                    event.stream_id,
                )
        for stream_id in stream_ids:
            self.server.send_headers(stream_id, RESPONSE, end_stream=True)
        response_wire = self.server.data_to_send()
        response_events = self.client.receive_data(response_wire)

        requests = sum(isinstance(event, H2RequestReceived) for event in request_events)
        body_bytes = sum(
            len(event.data)
            for event in request_events
            if isinstance(event, H2DataReceived)
        )
        responses = sum(
            isinstance(event, H2ResponseReceived) for event in response_events
        )
        return requests, body_bytes, responses


def time_workload(loops: int, workload: Ngh2RoundTrip | H2RoundTrip) -> float:
    """Measure repeated calls while keeping pyperf's loop overhead outside."""
    start = perf_counter()
    for _ in range(loops):
        workload()
    return perf_counter() - start


def check_workloads() -> None:
    """Verify both implementations complete each logical workload."""
    for _, _, headers, fragment_size, body_chunks, batch_size in SCENARIOS:
        expected = (batch_size, batch_size * sum(map(len, body_chunks)), batch_size)
        for workload_type in (Ngh2RoundTrip, H2RoundTrip):
            workload = workload_type(headers, fragment_size, body_chunks, batch_size)
            assert workload() == expected
            assert workload() == expected


def machine_name() -> str:
    """Return a stable processor label for result metadata."""
    if sys.platform == "darwin":
        result = subprocess.run(
            ("sysctl", "-n", "machdep.cpu.brand_string"),
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return platform.processor() or platform.machine()


def main() -> None:
    """Validate workloads and register them with pyperf."""
    check_workloads()

    def add_cmdline_args(command: list[str], args: argparse.Namespace) -> None:
        if args.scenario:
            command.extend(("--scenario", args.scenario))
        if args.implementation:
            command.extend(("--implementation", args.implementation))

    runner = pyperf.Runner(
        metadata={
            "ngh2_version": ngh2.__version__,
            "h2_version": h2.__version__,
            "machine_name": machine_name(),
        },
        add_cmdline_args=add_cmdline_args,
    )
    runner.argparser.add_argument(
        "--scenario",
        choices=[key for key, *_ in SCENARIOS],
    )
    runner.argparser.add_argument("--implementation", choices=("ngh2", "h2"))
    args = runner.parse_args()

    for key, _, headers, fragment_size, body_chunks, batch_size in SCENARIOS:
        if args.scenario and args.scenario != key:
            continue
        if args.implementation in (None, "ngh2"):
            runner.bench_time_func(
                f"scenario/{key}/ngh2",
                time_workload,
                Ngh2RoundTrip(headers, fragment_size, body_chunks, batch_size),
                inner_loops=batch_size,
            )
        if args.implementation in (None, "h2"):
            runner.bench_time_func(
                f"scenario/{key}/h2",
                time_workload,
                H2RoundTrip(headers, fragment_size, body_chunks, batch_size),
                inner_loops=batch_size,
            )


if __name__ == "__main__":
    main()
