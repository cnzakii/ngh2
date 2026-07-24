import ngh2


def transfer(source: ngh2.Connection, destination: ngh2.Connection) -> None:
    """Move every currently available byte between two protocol connections."""
    if data := source.data_to_send():
        destination.receive_data(data)


def main() -> None:
    client = ngh2.Connection(ngh2.Role.CLIENT)
    server = ngh2.Connection(ngh2.Role.SERVER)

    # RFC 9218 use starts with both endpoints declaring that the deprecated
    # RFC 7540 dependency-tree signal is not in use.
    settings = {ngh2.Setting.NO_RFC7540_PRIORITIES: 1}
    client.initiate_connection(settings)
    server.initiate_connection(settings)
    for source, destination in (
        (client, server),
        (server, client),
        (client, server),
        (server, client),
    ):
        transfer(source, destination)
    client.events()
    server.events()

    stream_id = client.send_request(
        [
            (b":method", b"GET"),
            (b":scheme", b"https"),
            (b":authority", b"example.test"),
            (b":path", b"/image.jpg"),
        ],
        end_stream=True,
    )
    transfer(client, server)
    server.events()

    # A client can reprioritize a response after opening its request stream.
    if not client.send_priority_update(stream_id, b"u=1, i"):
        raise RuntimeError("the server did not enable extensible priority")
    transfer(client, server)
    update = next(
        event
        for event in server.events()
        if isinstance(event, ngh2.PriorityUpdateReceived)
    )
    print(
        f"server received priority update {update.field_value!r} "
        f"for stream {update.prioritized_stream_id}"
    )

    # The application parses its priority policy and asks ngh2 to apply the
    # resulting urgency and incremental scheduling parameters.
    priority = ngh2.Priority(urgency=1, incremental=True)
    if not server.set_stream_priority(stream_id, priority):
        raise RuntimeError("extensible priority was not enabled locally")
    applied = server.get_stream_priority(stream_id)
    if applied is None:
        raise RuntimeError("the applied priority is unavailable")
    print(
        f"server scheduling priority: urgency={applied.urgency} "
        f"incremental={applied.incremental}"
    )


if __name__ == "__main__":
    main()
