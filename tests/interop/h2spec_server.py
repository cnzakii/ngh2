"""Minimal cleartext transport adapter used only by the h2spec runner."""

import argparse
import socket
from contextlib import suppress
from threading import Thread

from ngh2 import (
    Connection,
    DataReceived,
    GoAwayReceived,
    NGH2Error,
    RequestReceived,
    Role,
    StreamReset,
    TrailersReceived,
)


def send_response(
    connection: Connection,
    stream_id: int,
    method: bytes,
) -> None:
    """Queue the minimal response expected by h2spec message tests."""
    if method == b"HEAD":
        connection.send_response(
            stream_id,
            [(b":status", b"200")],
            end_stream=True,
        )
        return

    connection.send_response(
        stream_id,
        [(b":status", b"200"), (b"content-length", b"1")],
    )
    connection.send_data(stream_id, b"x", end_stream=True)


def serve_connection(transport: socket.socket) -> None:
    """Drive one ngh2 server session until the peer disconnects."""
    connection = Connection(Role.SERVER)
    requests: dict[int, bytes] = {}
    peer_goaway = False
    connection.initiate_connection()
    transport.sendall(connection.data_to_send())
    while data := transport.recv(65_536):
        try:
            connection.receive_data(data)
        except NGH2Error:
            with suppress(NGH2Error):
                if output := connection.data_to_send():
                    transport.sendall(output)
            return

        for event in connection.events():
            if isinstance(event, RequestReceived):
                method = next(
                    header[1] for header in event.headers if header[0] == b":method"
                )
                if event.end_stream:
                    send_response(connection, event.stream_id, method)
                else:
                    requests[event.stream_id] = method
            elif (isinstance(event, DataReceived) and event.end_stream) or isinstance(
                event, TrailersReceived
            ):
                method = requests.pop(event.stream_id, None)
                if method is not None:
                    send_response(connection, event.stream_id, method)
            elif isinstance(event, StreamReset):
                requests.pop(event.stream_id, None)
            elif isinstance(event, GoAwayReceived):
                peer_goaway = True
        if output := connection.data_to_send():
            transport.sendall(output)
        if peer_goaway:
            transport.shutdown(socket.SHUT_WR)
            while transport.recv(65_536):
                pass
            return


def handle_connection(transport: socket.socket) -> None:
    """Own and isolate one h2spec transport."""
    with (
        transport,
        suppress(
            BrokenPipeError,
            ConnectionError,
            NGH2Error,
            OSError,
        ),
    ):
        serve_connection(transport)


def main() -> None:
    """Accept h2spec connections until the process is terminated."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0)
    arguments = parser.parse_args()
    with socket.create_server(("127.0.0.1", arguments.port)) as listener:
        print(listener.getsockname()[1], flush=True)
        while True:
            transport, _ = listener.accept()
            Thread(
                target=handle_connection,
                args=(transport,),
                daemon=True,
            ).start()


if __name__ == "__main__":
    main()
