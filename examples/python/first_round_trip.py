import ngh2


def transfer(source: ngh2.Connection, destination: ngh2.Connection) -> None:
    """Move every currently available byte between two protocol connections."""
    if data := source.data_to_send():
        destination.receive_data(data)


def main() -> None:
    # One Connection represents one endpoint. The transport between the two
    # endpoints is deliberately replaced by transfer() in this first lesson.
    client = ngh2.Connection(ngh2.Role.CLIENT)
    server = ngh2.Connection(ngh2.Role.SERVER)
    client.initiate_connection()
    server.initiate_connection()

    # Each endpoint sends SETTINGS and then acknowledges the peer's SETTINGS,
    # so four one-way transfers complete connection setup.
    for source, destination in (
        (client, server),
        (server, client),
        (client, server),
        (server, client),
    ):
        transfer(source, destination)
    client.events()
    server.events()

    # The four pseudo-header fields describe an ordinary HTTPS GET request.
    # end_stream=True says there is no request body or request trailers.
    client.send_request(
        [
            (b":method", b"GET"),
            (b":scheme", b"https"),
            (b":authority", b"example.test"),
            (b":path", b"/hello"),
        ],
        end_stream=True,
    )
    transfer(client, server)

    # Incoming bytes become events. The server uses the stream ID from the
    # request event when it sends the matching response.
    request = next(
        event for event in server.events() if isinstance(event, ngh2.RequestReceived)
    )
    method = dict(request.headers)[b":method"].decode()
    path = dict(request.headers)[b":path"].decode()
    print(f"server received {method} {path} on stream {request.stream_id}")

    body = b"Hello over HTTP/2\n"
    # Response headers open the response body; the following DATA ends it.
    server.send_response(
        request.stream_id,
        [
            (b":status", b"200"),
            (b"content-length", str(len(body)).encode()),
        ],
    )
    server.send_data(request.stream_id, body, end_stream=True)
    transfer(server, client)

    # A body can span several DataReceived events. This small response fits in
    # one event, which keeps the first lesson focused on the driver cycle.
    events = client.events()
    response = next(
        event for event in events if isinstance(event, ngh2.ResponseReceived)
    )
    data = next(event for event in events if isinstance(event, ngh2.DataReceived))
    status = dict(response.headers)[b":status"].decode()
    print(f"client received {status} with {data.data!r}")


if __name__ == "__main__":
    main()
