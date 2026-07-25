import ngh2


def transfer(source: ngh2.Connection, destination: ngh2.Connection) -> None:
    """Move every currently available byte between two protocol connections."""
    if data := source.data_to_send():
        destination.receive_data(data)


def handshake(client: ngh2.Connection, server: ngh2.Connection) -> None:
    """Exchange initial SETTINGS and leave both event queues empty."""
    client.initiate_connection()
    server.initiate_connection()
    for source, destination in (
        (client, server),
        (server, client),
        (client, server),
        (server, client),
    ):
        transfer(source, destination)
    client.events()
    server.events()


def request(client: ngh2.Connection, server: ngh2.Connection, path: bytes) -> int:
    """Open one GET request and deliver it to the server."""
    stream_id = client.send_request(
        [
            (b":method", b"GET"),
            (b":scheme", b"https"),
            (b":authority", b"example.test"),
            (b":path", path),
        ],
        end_stream=True,
    )
    transfer(client, server)
    server.events()
    return stream_id


def main() -> None:
    client = ngh2.Connection(ngh2.Role.CLIENT)
    server = ngh2.Connection(ngh2.Role.SERVER)
    handshake(client, server)
    parent_id = request(client, server, b"/")

    # A push promise describes the request the server predicts. The returned
    # even stream ID carries the pushed response.
    pushed_id = server.send_push_promise(
        parent_id,
        [
            (b":method", b"GET"),
            (b":scheme", b"https"),
            (b":authority", b"example.test"),
            (b":path", b"/style.css"),
        ],
    )
    server.send_response(pushed_id, [(b":status", b"200")])
    server.send_data(pushed_id, b"body {}", end_stream=True)
    server.send_response(parent_id, [(b":status", b"204")], end_stream=True)
    transfer(server, client)

    pushed_path = b""
    pushed_body = bytearray()
    for event in client.events():
        if isinstance(event, ngh2.PushedStreamReceived):
            pushed_path = dict(event.headers)[b":path"]
            print(
                f"client accepted push {event.promised_stream_id} "
                f"for {pushed_path.decode()}"
            )
        elif isinstance(event, ngh2.DataReceived) and event.stream_id == pushed_id:
            pushed_body.extend(event.data)
        elif isinstance(event, ngh2.StreamClosed) and event.stream_id == pushed_id:
            if event.local_error is not None:
                raise event.local_error
            if event.error_code != ngh2.ErrorCode.NO_ERROR:
                raise RuntimeError(
                    f"push {pushed_id} closed with error {event.error_code}"
                )
            print(f"pushed response body: {bytes(pushed_body)!r}")

    # Clients can disable future push. If a queued promise later becomes
    # invalid, its reserved stream closes with the local reason attached.
    client.update_settings({ngh2.Setting.ENABLE_PUSH: 0})
    transfer(client, server)
    transfer(server, client)
    client.events()
    server.events()
    second_parent = request(client, server, b"/without-push")
    ignored_id = server.send_push_promise(
        second_parent,
        [
            (b":method", b"GET"),
            (b":scheme", b"https"),
            (b":authority", b"example.test"),
            (b":path", b"/ignored.css"),
        ],
    )
    server.data_to_send()
    closed = next(
        event
        for event in server.events()
        if isinstance(event, ngh2.StreamClosed) and event.stream_id == ignored_id
    )
    print(f"disabled push reported as {type(closed.local_error).__name__}")


if __name__ == "__main__":
    main()
