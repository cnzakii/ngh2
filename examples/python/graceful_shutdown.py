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
    server = ngh2.Connection(ngh2.Role.SERVER)
    handshake(client, server)

    stream_id = client.send_request(
        [
            (b":method", b"GET"),
            (b":scheme", b"https"),
            (b":authority", b"example.test"),
            (b":path", b"/in-flight"),
        ],
        end_stream=True,
    )
    transfer(client, server)
    server.events()

    # The first GOAWAY uses the largest stream ID. It stops new requests
    # without excluding a request that raced with the shutdown notice.
    server.send_shutdown_notice()
    transfer(server, client)
    notice = next(
        event for event in client.events() if isinstance(event, ngh2.GoAwayReceived)
    )
    print(f"server stopped new streams after GOAWAY {notice.last_stream_id}")
    print(f"client can open another request: {client.can_send_request}")

    # A real server waits at least one round-trip time before this final GOAWAY.
    # The final last_stream_id records the newest request that may be processed.
    server.send_goaway(last_stream_id=stream_id)
    transfer(server, client)
    final = next(
        event for event in client.events() if isinstance(event, ngh2.GoAwayReceived)
    )
    print(f"final GOAWAY covers streams through {final.last_stream_id}")

    # GOAWAY does not cancel an accepted stream. The server can finish it
    # before the application closes its caller-owned transport.
    server.send_response(stream_id, [(b":status", b"204")], end_stream=True)
    transfer(server, client)
    events = client.events()
    closed = next(
        event
        for event in events
        if isinstance(event, ngh2.StreamClosed) and event.stream_id == stream_id
    )
    if closed.local_error is not None:
        raise closed.local_error
    if closed.error_code != ngh2.ErrorCode.NO_ERROR:
        raise RuntimeError(f"stream {stream_id} closed with error {closed.error_code}")
    connection_closed = next(
        event for event in events if isinstance(event, ngh2.ConnectionClosed)
    )
    if connection_closed.error_code != ngh2.ErrorCode.NO_ERROR:
        raise RuntimeError(
            f"connection closed with error {connection_closed.error_code}"
        )
    print(f"in-flight stream {stream_id} completed")


if __name__ == "__main__":
    main()
