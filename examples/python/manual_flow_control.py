import ngh2


def transfer(source: ngh2.Connection, destination: ngh2.Connection) -> None:
    """Move every currently available byte between two protocol connections."""
    if data := source.data_to_send():
        destination.receive_data(data)


def handshake(client: ngh2.Connection, server: ngh2.Connection) -> None:
    """Exchange initial SETTINGS and leave both event queues empty."""
    client.initiate_connection()
    server.initiate_connection()
    # Each side sends SETTINGS and then acknowledges the peer's SETTINGS.
    for source, destination in (
        (client, server),
        (server, client),
        (client, server),
        (server, client),
    ):
        transfer(source, destination)
    client.events()
    server.events()


def consume_available_data(connection: ngh2.Connection) -> int:
    """Consume current DATA events and release exactly that receive capacity."""
    consumed = 0
    for event in connection.events():
        if isinstance(event, ngh2.DataReceived):
            consumed += len(event.data)
            # Manual mode ties WINDOW_UPDATE to application consumption. Frame
            # padding is accounted for by ngh2 and must not be added here.
            connection.acknowledge_received_data(len(event.data), event.stream_id)
    return consumed


def main() -> None:
    client = ngh2.Connection(ngh2.Role.CLIENT)
    # Manual receive-window updates let downstream consumption control when
    # the peer may send more body bytes.
    server = ngh2.Connection(
        ngh2.Role.SERVER,
        ngh2.Configuration(auto_window_update=False),
    )
    handshake(client, server)

    stream_id = client.send_request(
        [
            (b":method", b"POST"),
            (b":scheme", b"https"),
            (b":authority", b"example.test"),
            (b":path", b"/upload"),
        ],
    )
    body = b"x" * 70_000
    chunk_size = 20_000
    offset = 0
    received = 0

    # Submit one bounded chunk at a time. WINDOW_UPDATE frames stay at the
    # server for this short demonstration, so the fourth chunk exhausts the
    # initial 65,535-byte stream window and leaves a visible queued tail.
    while offset < len(body) and client.queued_body_size(stream_id) == 0:
        end = min(offset + chunk_size, len(body))
        client.send_data(
            stream_id,
            body[offset:end],
            end_stream=end == len(body),
        )
        offset = end
        transfer(client, server)
        received += consume_available_data(server)

    print(
        f"application consumed {received:,} bytes; "
        f"{client.queued_body_size(stream_id):,} remain queued"
    )

    # Return the accumulated WINDOW_UPDATE frames. The next output drive can
    # then take the queued tail and complete the request body.
    transfer(server, client)
    client.events()
    while client.queued_body_size(stream_id):
        transfer(client, server)
        received += consume_available_data(server)
        print(
            f"application consumed {received:,} bytes; "
            f"{client.queued_body_size(stream_id):,} remain queued"
        )

    print(f"upload complete: {received:,} bytes")


if __name__ == "__main__":
    main()
