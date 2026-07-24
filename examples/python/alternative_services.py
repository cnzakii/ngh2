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


def main() -> None:
    client = ngh2.Connection(ngh2.Role.CLIENT)
    server = ngh2.Connection(ngh2.Role.SERVER)
    handshake(client, server)

    # ALTSVC carries the raw Alt-Svc field value. This connection-level form
    # names the origin whose alternative service is being advertised.
    server.send_alt_svc(
        b'h3=":443"; ma=3600',
        origin=b"https://example.test",
    )
    # ORIGIN advertises origins that may share this authenticated connection.
    server.send_origins(
        [
            b"https://example.test",
            b"https://cdn.example.test",
        ]
    )
    transfer(server, client)

    for event in client.events():
        if isinstance(event, ngh2.AltSvcReceived):
            print(
                f"alternative for {event.origin.decode()}: {event.field_value.decode()}"
            )
        elif isinstance(event, ngh2.OriginReceived):
            origins = ", ".join(origin.decode() for origin in event.origins)
            print(f"connection origin set: {origins}")

    # ngh2 reports advertisements as protocol data. A real client still owns
    # parsing, freshness, connection selection, and certificate validation.


if __name__ == "__main__":
    main()
