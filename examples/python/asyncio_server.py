import argparse
import asyncio
import logging
import ssl
from contextlib import suppress

import ngh2

LOGGER = logging.getLogger(__name__)


def send_response(
    connection: ngh2.Connection,
    stream_id: int,
    headers: tuple[ngh2.Header, ...],
) -> None:
    """Queue the response for one complete request."""
    request = dict(headers)
    method = request[b":method"]
    path = request[b":path"]

    if method not in (b"GET", b"HEAD"):
        status = b"405"
        body = b"Method not allowed\n"
    elif path != b"/":
        status = b"404"
        body = b"Not found\n"
    else:
        status = b"200"
        body = b"Hello over HTTP/2\n"

    response_headers = [
        (b":status", status),
        (b"content-type", b"text/plain; charset=utf-8"),
        (b"content-length", str(len(body)).encode()),
    ]
    if status == b"405":
        response_headers.append((b"allow", b"GET, HEAD"))
    # HEAD carries the same headers as GET but never sends the response body.
    if method == b"HEAD":
        connection.send_response(stream_id, response_headers, end_stream=True)
    else:
        connection.send_response(stream_id, response_headers)
        connection.send_data(stream_id, body, end_stream=True)


def process_request_events(
    connection: ngh2.Connection,
    requests: dict[int, tuple[ngh2.Header, ...]],
) -> bool:
    """Route connection events and respond after each request body ends."""
    closed = False
    ready: set[int] = set()
    for event in connection.events():
        if isinstance(event, ngh2.RequestReceived):
            requests[event.stream_id] = event.headers
            if event.end_stream:
                ready.add(event.stream_id)
        elif (isinstance(event, ngh2.DataReceived) and event.end_stream) or isinstance(
            event, ngh2.TrailersReceived
        ):
            if event.stream_id in requests:
                ready.add(event.stream_id)
        elif isinstance(event, ngh2.StreamReset):
            requests.pop(event.stream_id, None)
            ready.discard(event.stream_id)
        elif isinstance(event, ngh2.StreamClosed):
            requests.pop(event.stream_id, None)
            ready.discard(event.stream_id)
            if event.local_error is not None:
                # A delayed local failure ends this stream, not its siblings.
                LOGGER.error("stream %d failed: %s", event.stream_id, event.local_error)
            elif event.error_code != ngh2.ErrorCode.NO_ERROR:
                LOGGER.warning(
                    "stream %d closed with error %d",
                    event.stream_id,
                    event.error_code,
                )
        elif isinstance(event, ngh2.ConnectionClosed):
            closed = True
    if not closed:
        for stream_id in ready:
            headers = requests.pop(stream_id, None)
            if headers is not None:
                send_response(connection, stream_id, headers)
    return closed


async def handle_connection(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    """Own one TLS transport and its matching HTTP/2 connection."""
    ssl_object = writer.get_extra_info("ssl_object")
    if ssl_object is None or ssl_object.selected_alpn_protocol() != "h2":
        writer.close()
        with suppress(ConnectionError, ssl.SSLError):
            await writer.wait_closed()
        return

    # Each accepted socket gets an independent Connection. This coroutine is
    # its only owner, so protocol actions remain serialized in wire order.
    connection = ngh2.Connection(ngh2.Role.SERVER)
    requests: dict[int, tuple[ngh2.Header, ...]] = {}
    connection.initiate_connection()

    try:
        while True:
            outgoing = connection.data_to_send()
            if outgoing:
                writer.write(outgoing)
                await writer.drain()
            if process_request_events(connection, requests):
                break

            incoming = await reader.read(65_536)
            if not incoming:
                break
            connection.receive_data(incoming)
            if process_request_events(connection, requests):
                break
    finally:
        writer.close()
        with suppress(ConnectionError, ssl.SSLError):
            await writer.wait_closed()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Serve HTTP/2 over TLS with ngh2")
    parser.add_argument("certfile", help="PEM certificate chain")
    parser.add_argument("keyfile", help="PEM private key")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8443)
    args = parser.parse_args()

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(args.certfile, args.keyfile)
    context.set_alpn_protocols(["h2"])

    server = await asyncio.start_server(
        handle_connection,
        args.host,
        args.port,
        ssl=context,
    )
    print(f"serving HTTPS on {args.host}:{args.port}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
