"""Track the ngh2 side of the h2 comparison scenarios with CodSpeed.

The large-body workload is ngh2-only: it covers DATA framing and reassembly
when transport reads do not line up with frame boundaries.
"""

import pytest
from compare_h2 import SCENARIOS, Ngh2Exchange

import ngh2

LARGE_BODY = b"x" * (1024 * 1024)
LARGE_BODY_REQUEST = (
    (b":method", b"POST"),
    (b":scheme", b"https"),
    (b":authority", b"example.test"),
    (b":path", b"/upload"),
    (b"content-length", str(len(LARGE_BODY)).encode()),
)


@pytest.mark.parametrize(
    "scenario",
    [scenario for _, _, scenario in SCENARIOS],
    ids=[f"http2_{key}" for key, _, _ in SCENARIOS],
)
def test_exchange(benchmark, scenario):
    workload = Ngh2Exchange(scenario)
    # The first iteration fills the HPACK dynamic tables; later ones reuse them.
    workload()

    assert benchmark(workload) == scenario.expected()


def test_large_body_socket_reads(benchmark):
    """Upload 1 MiB between peers that allow large frames, read 64 KiB at a time."""
    window = 16 * 1024 * 1024
    client = ngh2.Connection(ngh2.Role.CLIENT)
    server = ngh2.Connection(ngh2.Role.SERVER)
    for connection in (client, server):
        connection.initiate_connection(
            {
                ngh2.Setting.INITIAL_WINDOW_SIZE: window,
                ngh2.Setting.MAX_FRAME_SIZE: 1024 * 1024,
            },
        )
        connection.set_local_window_size(window)
    for source, destination in ((client, server), (server, client)) * 2:
        destination.receive_data(source.data_to_send())
    client.events()
    server.events()

    def upload() -> int:
        stream_id = client.send_request(LARGE_BODY_REQUEST)
        client.send_data(stream_id, LARGE_BODY, end_stream=True)
        wire = client.data_to_send()
        for offset in range(0, len(wire), 65_536):
            server.receive_data(wire[offset : offset + 65_536])
        received = sum(
            len(event.data)
            for event in server.events()
            if isinstance(event, ngh2.DataReceived)
        )
        server.send_response(stream_id, ((b":status", b"204"),), end_stream=True)
        client.receive_data(server.data_to_send())
        client.events()
        return received

    upload()

    assert benchmark(upload) == len(LARGE_BODY)
