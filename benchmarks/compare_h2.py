"""Compare complete HTTP/2 exchanges through the public APIs of ngh2 and h2.

Each scenario sends one request, or ten concurrent requests on one connection,
with a request or response body of the given size. "Writes" are separate
send_data() calls for one request body. "Max window" raises the stream and
connection flow-control windows on both peers to 2**31 - 1; other scenarios
keep each library's default settings.

One iteration completes every request and reads every response body. Each
library talks to itself in memory, and each side reads its peer's output in
64 KiB pieces. Work a library leaves to its caller is timed with it: h2 callers
split bodies to the flow-control window and frame size and acknowledge
received data, while ngh2 does both natively. Every run checks that both
libraries deliver the same requests, responses, and body bytes.
"""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from dataclasses import dataclass
from time import perf_counter

import h2
import h2.events
import pyperf
from h2.config import H2Configuration
from h2.connection import H2Connection
from h2.settings import SettingCodes, Settings

import ngh2

Headers = tuple[tuple[bytes, bytes], ...]

READ_SIZE = 65_536
DEFAULT_WINDOW = 65_535
# Applied to stream and connection windows on both peers.
MAX_WINDOW = 2**31 - 1


@dataclass(frozen=True)
class Scenario:
    """One benchmark: request count, body sizes, and window settings."""

    parallel: int = 1
    request_body: bytes = b""
    request_chunks: int = 0
    response_body: bytes = b""
    window: int | None = None

    @property
    def request_parts(self) -> tuple[bytes, ...]:
        if self.request_chunks:
            return (self.request_body,) * self.request_chunks
        return (self.request_body,) if self.request_body else ()

    @property
    def request(self) -> Headers:
        method = b"POST" if self.request_body else b"GET"
        headers = (
            (b":method", method),
            (b":scheme", b"http"),
            (b":authority", b"127.0.0.1"),
            (b":path", b"/hello"),
        )
        # A complete body has a known length; a chunked stream does not.
        if self.request_body and not self.request_chunks:
            headers += ((b"content-length", b"%d" % len(self.request_body)),)
        return headers

    @property
    def response(self) -> Headers:
        return (
            (b":status", b"200"),
            (b"content-length", b"%d" % len(self.response_body)),
        )

    def expected(self) -> tuple[int, int, int, int]:
        """Return the totals each library must report for one iteration."""
        return (
            self.parallel,
            self.parallel * sum(map(len, self.request_parts)),
            self.parallel,
            self.parallel * len(self.response_body),
        )


KB = 1024
MB = 1024 * 1024
SCENARIOS = (
    ("consecutive_x1_empty", "1 request · no body", Scenario()),
    (
        "consecutive_x1_req_10b",
        "1 request · 10 B upload",
        Scenario(request_body=b"s" * 10),
    ),
    (
        "consecutive_x1_req_100kb",
        "1 request · 100 KiB upload",
        Scenario(request_body=b"x" * (100 * KB)),
    ),
    ("parallel_x10_empty", "10 concurrent requests · no body", Scenario(parallel=10)),
    (
        "parallel_x10_req_10mb",
        "10 concurrent · 10 MiB upload each · max window",
        Scenario(parallel=10, request_body=b"x" * (10 * MB), window=MAX_WINDOW),
    ),
    (
        "parallel_x10_req_10kb_100_chunks",
        "10 concurrent · 100 writes of 10 KiB upload each",
        Scenario(parallel=10, request_body=b"x" * (10 * KB), request_chunks=100),
    ),
    (
        "parallel_x10_req_10kb_100_chunks_max_window",
        "10 concurrent · 100 writes of 10 KiB upload each · max window",
        Scenario(
            parallel=10,
            request_body=b"x" * (10 * KB),
            request_chunks=100,
            window=MAX_WINDOW,
        ),
    ),
    (
        "parallel_x10_res_1mb",
        "10 concurrent · 1 MiB download each · max window",
        Scenario(parallel=10, response_body=b"x" * MB, window=MAX_WINDOW),
    ),
    (
        "parallel_x10_res_10mb",
        "10 concurrent · 10 MiB download each · max window",
        Scenario(parallel=10, response_body=b"x" * (10 * MB), window=MAX_WINDOW),
    ),
)


class Ngh2Exchange:
    """Run one scenario's iterations with an ngh2 client and server."""

    __slots__ = ("client", "scenario", "server", "totals")

    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self.totals = [0] * 4
        self.client = ngh2.Connection(ngh2.Role.CLIENT)
        self.server = ngh2.Connection(ngh2.Role.SERVER)
        window = scenario.window
        for connection in (self.client, self.server):
            if window is None:
                connection.initiate_connection()
            else:
                connection.initiate_connection(
                    {ngh2.Setting.INITIAL_WINDOW_SIZE: window},
                )
                connection.set_local_window_size(window)
        self.pump()

    def __call__(self) -> tuple[int, ...]:
        scenario = self.scenario
        self.totals = [0] * 4
        parts = scenario.request_parts
        last = len(parts) - 1
        for _ in range(scenario.parallel):
            stream_id = self.client.send_request(scenario.request, end_stream=not parts)
            for index, part in enumerate(parts):
                self.client.send_data(stream_id, part, end_stream=index == last)
        self.pump()
        return tuple(self.totals)

    def pump(self) -> None:
        """Move bytes both ways until neither peer has anything to send."""
        while self.deliver(at_server=True) | self.deliver(at_server=False):
            pass

    def deliver(self, *, at_server: bool) -> bool:
        source, destination = self.client, self.server
        if not at_server:
            source, destination = destination, source
        wire = source.data_to_send()
        totals = self.totals
        for offset in range(0, len(wire), READ_SIZE):
            destination.receive_data(wire[offset : offset + READ_SIZE])
            for event in destination.events():
                if isinstance(event, ngh2.DataReceived):
                    totals[1 if at_server else 3] += len(event.data)
                    if at_server and event.end_stream:
                        self.respond(event.stream_id)
                elif isinstance(event, ngh2.RequestReceived):
                    totals[0] += 1
                    if event.end_stream:
                        self.respond(event.stream_id)
                elif isinstance(event, ngh2.ResponseReceived):
                    totals[2] += 1
        return bool(wire)

    def respond(self, stream_id: int) -> None:
        body = self.scenario.response_body
        self.server.send_response(
            stream_id, self.scenario.response, end_stream=not body
        )
        if body:
            self.server.send_data(stream_id, body, end_stream=True)


class H2Exchange:
    """Run one scenario's iterations with an h2 client and server."""

    __slots__ = ("client", "pending", "scenario", "server", "totals")

    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self.totals = [0] * 4
        self.client = self.open(client_side=True)
        self.server = self.open(client_side=False)
        self.pending: dict[H2Connection, dict[int, list[list]]] = {
            self.client: {},
            self.server: {},
        }
        self.pump()

    def open(self, *, client_side: bool) -> H2Connection:
        connection = H2Connection(H2Configuration(client_side=client_side))
        window = self.scenario.window
        if window is not None:
            connection.local_settings = Settings(
                client=client_side,
                initial_values={SettingCodes.INITIAL_WINDOW_SIZE: window},
            )
        connection.initiate_connection()
        if window is not None:
            connection.increment_flow_control_window(window - DEFAULT_WINDOW)
        return connection

    def __call__(self) -> tuple[int, ...]:
        scenario = self.scenario
        self.totals = [0] * 4
        parts = scenario.request_parts
        last = len(parts) - 1
        for _ in range(scenario.parallel):
            stream_id = self.client.get_next_available_stream_id()
            self.client.send_headers(stream_id, scenario.request, end_stream=not parts)
            for index, part in enumerate(parts):
                self.send_data(self.client, stream_id, part, end_stream=index == last)
        self.pump()
        return tuple(self.totals)

    def send_data(
        self,
        connection: H2Connection,
        stream_id: int,
        data: bytes,
        *,
        end_stream: bool,
    ) -> None:
        """Queue body bytes; deliver() frames them as flow control allows."""
        self.pending[connection].setdefault(stream_id, []).append(
            [data, 0, end_stream],
        )

    def flush(self, connection: H2Connection) -> None:
        pending = self.pending[connection]
        for stream_id in list(pending):
            queue = pending[stream_id]
            while queue:
                data, offset, end_stream = queue[0]
                remaining = len(data) - offset
                size = min(
                    remaining,
                    connection.local_flow_control_window(stream_id),
                    connection.max_outbound_frame_size,
                )
                if size == 0 and remaining:
                    break
                # Slice one frame at a time; slicing off the remainder would
                # copy large bodies once per frame.
                connection.send_data(
                    stream_id,
                    data[offset : offset + size],
                    end_stream=end_stream and size == remaining,
                )
                if size == remaining:
                    queue.pop(0)
                else:
                    queue[0][1] = offset + size
            if not queue:
                del pending[stream_id]

    def pump(self) -> None:
        """Move bytes both ways until neither peer has anything to send."""
        while self.deliver(at_server=True) | self.deliver(at_server=False):
            pass

    def deliver(self, *, at_server: bool) -> bool:
        source, destination = self.client, self.server
        if not at_server:
            source, destination = destination, source
        self.flush(source)
        wire = source.data_to_send()
        totals = self.totals
        for offset in range(0, len(wire), READ_SIZE):
            for event in destination.receive_data(wire[offset : offset + READ_SIZE]):
                if isinstance(event, h2.events.DataReceived):
                    totals[1 if at_server else 3] += len(event.data)
                    destination.acknowledge_received_data(
                        event.flow_controlled_length,
                        event.stream_id,
                    )
                elif isinstance(event, h2.events.RequestReceived):
                    totals[0] += 1
                elif isinstance(event, h2.events.ResponseReceived):
                    totals[2] += 1
                elif isinstance(event, h2.events.StreamEnded) and at_server:
                    self.respond(event.stream_id)
        return bool(wire)

    def respond(self, stream_id: int) -> None:
        body = self.scenario.response_body
        self.server.send_headers(stream_id, self.scenario.response, end_stream=not body)
        if body:
            self.send_data(self.server, stream_id, body, end_stream=True)


IMPLEMENTATIONS = {"ngh2": Ngh2Exchange, "h2": H2Exchange}


def time_workload(loops: int, workload: Ngh2Exchange | H2Exchange) -> float:
    """Measure repeated calls while keeping pyperf's loop overhead outside."""
    start = perf_counter()
    for _ in range(loops):
        workload()
    return perf_counter() - start


def check_workloads() -> None:
    """Verify both implementations deliver the same totals for each scenario."""
    for key, _, scenario in SCENARIOS:
        expected = scenario.expected()
        for name, implementation in IMPLEMENTATIONS.items():
            workload = implementation(scenario)
            for _ in range(2):
                result = workload()
                assert result == expected, (key, name, result, expected)


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


def source_revision() -> str | None:
    """Return the measured checkout, marked when it has uncommitted changes."""
    result = subprocess.run(
        ("git", "describe", "--always", "--dirty"),
        capture_output=True,
        check=False,
        text=True,
    )
    return result.stdout.strip() or None


def main() -> None:
    """Validate workloads and register them with pyperf."""
    # pyperf re-runs this module in each worker; validate once, in the parent.
    if "--worker" not in sys.argv:
        check_workloads()

    def add_cmdline_args(command: list[str], args: argparse.Namespace) -> None:
        if args.scenario:
            command.extend(("--scenario", args.scenario))
        if args.implementation:
            command.extend(("--implementation", args.implementation))

    metadata = {
        "ngh2_version": ngh2.__version__,
        "h2_version": h2.__version__,
        "machine_name": machine_name(),
    }
    if revision := source_revision():
        metadata["ngh2_revision"] = revision
    runner = pyperf.Runner(
        metadata=metadata,
        add_cmdline_args=add_cmdline_args,
    )
    runner.argparser.add_argument(
        "--scenario",
        choices=[key for key, _, _ in SCENARIOS],
    )
    runner.argparser.add_argument("--implementation", choices=tuple(IMPLEMENTATIONS))
    args = runner.parse_args()

    for key, _, scenario in SCENARIOS:
        if args.scenario and args.scenario != key:
            continue
        for name, implementation in IMPLEMENTATIONS.items():
            if args.implementation in (None, name):
                runner.bench_time_func(
                    f"http2_{key}/{name}",
                    time_workload,
                    implementation(scenario),
                )


if __name__ == "__main__":
    main()
