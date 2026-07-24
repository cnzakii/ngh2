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
    # The body is larger than the initial stream window, so ngh2 must retain
    # some bytes until the server releases receive-window capacity.
    body = b"x" * 70_000
    client.send_data(stream_id, body, end_stream=True)

    received = 0
    while client.pending_data(stream_id):
        transfer(client, server)

        for event in server.events():
            if isinstance(event, ngh2.DataReceived):
                received += len(event.data)
                # Acknowledge only bytes the application has consumed. Frame
                # padding is accounted for by ngh2 and must not be added here.
                server.acknowledge_received_data(len(event.data), event.stream_id)

        # The acknowledgement queues WINDOW_UPDATE frames. Returning them to
        # the client lets its next data_to_send() call resume the upload.
        transfer(server, client)
        client.events()
        print(
            f"application consumed {received:,} bytes; "
            f"{client.pending_data(stream_id):,} remain queued"
        )

    print(f"upload complete: {received:,} bytes")


if __name__ == "__main__":
    main()
