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

    # Application state is keyed by stream ID because events from every active
    # request share the same connection-level event queue.
    paths_by_stream: dict[int, str] = {}
    for path in ("/slow", "/fast"):
        stream_id = client.send_request(
            [
                (b":method", b"GET"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", path.encode()),
            ],
            end_stream=True,
        )
        paths_by_stream[stream_id] = path
        print(f"client opened {path} on stream {stream_id}")

    transfer(client, server)
    requests = {
        event.stream_id: event
        for event in server.events()
        if isinstance(event, ngh2.RequestReceived)
    }

    # Finish /fast first. HTTP/2 does not require response completion order to
    # match request order.
    bodies: dict[int, bytearray] = {}
    for stream_id in reversed(requests):
        path = paths_by_stream[stream_id]
        body = f"response for {path}\n".encode()
        server.send_response(
            stream_id,
            [
                (b":status", b"200"),
                (b"content-length", str(len(body)).encode()),
            ],
        )
        server.send_data(stream_id, body, end_stream=True)
        transfer(server, client)

        # Route every event through event.stream_id. DataReceived is a chunk,
        # while StreamClosed is the reliable completion signal.
        for event in client.events():
            if isinstance(event, ngh2.ResponseReceived):
                bodies[event.stream_id] = bytearray()
            elif isinstance(event, ngh2.DataReceived):
                bodies[event.stream_id].extend(event.data)
            elif isinstance(event, ngh2.StreamClosed):
                completed_path = paths_by_stream[event.stream_id]
                completed_body = bytes(bodies.pop(event.stream_id))
                print(
                    f"client completed {completed_path}: "
                    f"{completed_body.decode().strip()}"
                )


if __name__ == "__main__":
    main()
