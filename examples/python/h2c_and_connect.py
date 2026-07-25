import ngh2


def transfer(source: ngh2.Connection, destination: ngh2.Connection) -> None:
    """Move every currently available byte between two protocol connections."""
    if data := source.data_to_send():
        destination.receive_data(data)


def main() -> None:
    settings = {ngh2.Setting.MAX_CONCURRENT_STREAMS: 10}

    # The HTTP/1.1 client base64url-encodes this binary payload for its
    # HTTP2-Settings header. ngh2 deliberately does not parse HTTP/1.1.
    payload = ngh2.pack_settings_payload(settings)
    print(f"binary HTTP2-Settings payload: {payload.hex()}")

    # This lesson starts after the application has sent and accepted the
    # HTTP/1.1 Upgrade request. Both sides initialize HTTP/2 from the decoded
    # payload; the upgraded request already occupies stream 1.
    client = ngh2.Connection(ngh2.Role.CLIENT)
    server = ngh2.Connection(ngh2.Role.SERVER)
    client.initiate_upgrade(payload)
    server.initiate_upgrade(payload, local_settings=settings)
    transfer(client, server)
    transfer(server, client)
    client.events()
    server.events()

    server.send_response(1, [(b":status", b"204")], end_stream=True)
    transfer(server, client)
    response = next(
        event for event in client.events() if isinstance(event, ngh2.ResponseReceived)
    )
    status = dict(response.headers)[b":status"].decode()
    print(f"client received {status} on upgraded stream {response.stream_id}")

    # Extended CONNECT is a separate HTTP/2 feature, not an h2c upgrade. A
    # client may use :protocol only after the server advertises support.
    client = ngh2.Connection(ngh2.Role.CLIENT)
    server = ngh2.Connection(ngh2.Role.SERVER)
    client.initiate_connection()
    server.initiate_connection({ngh2.Setting.ENABLE_CONNECT_PROTOCOL: 1})
    for source, destination in (
        (client, server),
        (server, client),
        (client, server),
        (server, client),
    ):
        transfer(source, destination)
    client.events()
    server.events()

    if client.remote_settings[ngh2.Setting.ENABLE_CONNECT_PROTOCOL] != 1:
        raise RuntimeError("the server did not enable extended CONNECT")
    connect_id = client.send_request(
        [
            (b":method", b"CONNECT"),
            (b":protocol", b"websocket"),
            (b":scheme", b"https"),
            (b":authority", b"example.test"),
            (b":path", b"/chat"),
        ]
    )
    transfer(client, server)
    request = next(
        event for event in server.events() if isinstance(event, ngh2.RequestReceived)
    )
    protocol = dict(request.headers)[b":protocol"].decode()
    print(f"server received extended CONNECT for {protocol} on stream {connect_id}")


if __name__ == "__main__":
    main()
