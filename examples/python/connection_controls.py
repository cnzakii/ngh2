import ngh2


def transfer(
    source: ngh2.Connection,
    destination: ngh2.Connection,
    amount: int | None = None,
) -> None:
    """Move schedulable bytes, optionally in transport-sized chunks."""
    while data := source.data_to_send(amount):
        destination.receive_data(data)


def handshake(client: ngh2.Connection, server: ngh2.Connection) -> None:
    """Exchange initial SETTINGS and leave both event queues empty."""
    client.initiate_connection()
    server.initiate_connection()
    # A byte limit can be used when a transport cannot accept all output at
    # once. Repeated calls continue from the same protocol state.
    transfer(client, server, amount=24)
    transfer(server, client)
    transfer(client, server)
    transfer(server, client)
    client.events()
    server.events()


def main() -> None:
    client = ngh2.Connection(ngh2.Role.CLIENT)
    server = ngh2.Connection(ngh2.Role.SERVER)
    handshake(client, server)

    # Query properties expose protocol state for a connection driver; they do
    # not replace events or make policy decisions.
    print(
        f"client role={client.role.value} next_stream={client.next_stream_id} "
        f"read={client.want_read} write={client.want_write}"
    )
    print(
        f"connection windows local={client.local_window_size} "
        f"remote={client.remote_window_size}"
    )

    # SETTINGS updates take effect for the peer when received and for the
    # sender's local_settings snapshot when acknowledged.
    client.update_settings({ngh2.Setting.MAX_FRAME_SIZE: 32_768})
    client.ping(b"health01")
    transfer(client, server)

    received = server.events()
    settings = next(
        event for event in received if isinstance(event, ngh2.SettingsReceived)
    )
    ping = next(event for event in received if isinstance(event, ngh2.PingReceived))
    print(
        f"server received max frame size {settings.settings[ngh2.Setting.MAX_FRAME_SIZE]}"
    )
    print(f"server received PING {ping.opaque_data!r}")

    # SETTINGS and PING acknowledgements are generated automatically but still
    # need to cross the caller-owned transport.
    transfer(server, client)
    acknowledgements = client.events()
    if any(isinstance(event, ngh2.SettingsAcknowledged) for event in acknowledgements):
        print(
            "client settings acknowledged at "
            f"{client.local_settings[ngh2.Setting.MAX_FRAME_SIZE]}"
        )
    ping_ack = next(
        event for event in acknowledgements if isinstance(event, ngh2.PingAcknowledged)
    )
    print(f"client received PING acknowledgement {ping_ack.opaque_data!r}")
    print(
        "server effective peer setting "
        f"{server.remote_settings[ngh2.Setting.MAX_FRAME_SIZE]}"
    )


if __name__ == "__main__":
    main()
