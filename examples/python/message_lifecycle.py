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

    # A request without end_stream=True keeps its local direction open for
    # body bytes and optional trailers.
    upload_id = client.send_request(
        [
            (b":method", b"POST"),
            (b":scheme", b"https"),
            (b":authority", b"example.test"),
            (b":path", b"/upload"),
        ]
    )
    client.send_data(upload_id, b"hello ")
    client.send_data(upload_id, b"world")
    # Trailers end the request direction after all queued body bytes.
    client.send_trailers(upload_id, [(b"digest", b"sha-256=:demo:")])
    transfer(client, server)

    request_body = bytearray()
    request_trailer = b""
    for event in server.events():
        if isinstance(event, ngh2.DataReceived) and event.stream_id == upload_id:
            request_body.extend(event.data)
        elif isinstance(event, ngh2.TrailersReceived):
            request_trailer = dict(event.headers)[b"digest"]
    print(
        f"server received {bytes(request_body)!r} "
        f"with digest {request_trailer.decode()}"
    )

    # Informational responses precede the one final response. Response trailers
    # then end the server's sending direction.
    server.send_informational_response(upload_id, [(b":status", b"103")])
    server.send_response(upload_id, [(b":status", b"200")])
    server.send_data(upload_id, b"stored")
    server.send_trailers(upload_id, [(b"result", b"accepted")])
    transfer(server, client)

    response_body = bytearray()
    response_result: str | None = None
    for event in client.events():
        if isinstance(event, ngh2.InformationalResponseReceived):
            print(
                f"client received informational {dict(event.headers)[b':status'].decode()}"
            )
        elif isinstance(event, ngh2.ResponseReceived):
            print(f"client received final {dict(event.headers)[b':status'].decode()}")
        elif isinstance(event, ngh2.DataReceived):
            response_body.extend(event.data)
        elif isinstance(event, ngh2.TrailersReceived):
            response_result = dict(event.headers)[b"result"].decode()
        elif isinstance(event, ngh2.StreamClosed) and event.stream_id == upload_id:
            if event.local_error is not None:
                raise event.local_error
            if event.error_code != ngh2.ErrorCode.NO_ERROR:
                raise RuntimeError(f"upload closed with error {event.error_code}")
            if response_result is None:
                raise RuntimeError("response closed without result trailers")
            print(
                f"client received {bytes(response_body)!r} "
                f"with result {response_result}"
            )

    # end_stream() is the explicit form for ending an open body without adding
    # bytes or trailers. A peer can instead cancel the stream with RST_STREAM.
    cancelled_id = client.send_request(
        [
            (b":method", b"POST"),
            (b":scheme", b"https"),
            (b":authority", b"example.test"),
            (b":path", b"/cancel"),
        ]
    )
    client.end_stream(cancelled_id)
    transfer(client, server)
    server.events()
    server.reset_stream(cancelled_id, ngh2.ErrorCode.CANCEL)
    transfer(server, client)
    reset = next(
        event for event in client.events() if isinstance(event, ngh2.StreamReset)
    )
    print(f"client observed CANCEL on stream {reset.stream_id}")


if __name__ == "__main__":
    main()
