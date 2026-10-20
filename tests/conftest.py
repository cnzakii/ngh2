from collections.abc import Callable

import pytest

from ngh2 import Connection


@pytest.fixture
def handshake() -> Callable[[Connection, Connection], None]:
    """Initiate two existing connections and consume their SETTINGS events."""

    def exchange_settings(client: Connection, server: Connection) -> None:
        client.initiate_connection()
        server.initiate_connection()
        for _ in range(2):
            server.receive_data(client.data_to_send())
            client.receive_data(server.data_to_send())
        client.events()
        server.events()

    return exchange_settings
