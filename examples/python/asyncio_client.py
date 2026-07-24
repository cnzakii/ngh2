import argparse
import asyncio
import ssl
from contextlib import suppress
from urllib.parse import urlsplit

import ngh2


def process_response_events(
    connection: ngh2.Connection,
    stream_id: int,
    status: int | None,
    body: bytearray,
) -> tuple[int | None, bool]:
    """Apply queued events for one request and report stream completion."""
    complete = False
    for event in connection.events():
        if isinstance(event, ngh2.ResponseReceived) and event.stream_id == stream_id:
            status = int(dict(event.headers)[b":status"])
        elif isinstance(event, ngh2.DataReceived) and event.stream_id == stream_id:
            # A response body can be split across any number of DATA frames.
            body.extend(event.data)
        elif isinstance(event, ngh2.StreamReset) and event.stream_id == stream_id:
            raise RuntimeError(
                f"stream {stream_id} was reset with error {event.error_code}"
            )
        elif isinstance(event, ngh2.FrameNotSent):
            # data_to_send() reports delayed frame failures through events.
            raise event.error
        elif (
            isinstance(event, ngh2.GoAwayReceived) and stream_id > event.last_stream_id
        ):
            raise RuntimeError(f"the peer did not process stream {stream_id}")
        elif isinstance(event, ngh2.StreamClosed) and event.stream_id == stream_id:
            complete = True
    return status, complete


async def get(url: str) -> tuple[int, bytes]:
    target = urlsplit(url)
    if target.scheme != "https" or not target.hostname:
        raise ValueError("URL must be an absolute https URL")

    # TLS negotiates HTTP/2 before any application bytes reach ngh2. The
    # default context keeps certificate and hostname verification enabled.
    context = ssl.create_default_context()
    context.set_alpn_protocols(["h2"])
    port = target.port or 443
    reader, writer = await asyncio.open_connection(
        target.hostname,
        port,
        ssl=context,
        server_hostname=target.hostname,
    )

    ssl_object = writer.get_extra_info("ssl_object")
    if ssl_object is None or ssl_object.selected_alpn_protocol() != "h2":
        writer.close()
        with suppress(ssl.SSLError):
            await writer.wait_closed()
        raise RuntimeError("the server did not negotiate HTTP/2 with ALPN")

    try:
        # One coroutine owns the Connection and serializes every protocol action.
        connection = ngh2.Connection(ngh2.Role.CLIENT)
        connection.initiate_connection()
        path = target.path or "/"
        if target.query:
            path = f"{path}?{target.query}"
        authority = target.hostname
        if target.port is not None:
            authority = f"{authority}:{target.port}"
        stream_id = connection.send_request(
            [
                (b":method", b"GET"),
                (b":scheme", b"https"),
                (b":authority", authority.encode("ascii")),
                (b":path", path.encode("ascii")),
                (b"user-agent", b"ngh2-example"),
            ],
            end_stream=True,
        )

        # Queueing a request does not touch the socket. data_to_send() returns
        # the preface, SETTINGS, and currently schedulable request bytes.
        outgoing = connection.data_to_send()
        status: int | None = None
        body = bytearray()
        status, complete = process_response_events(
            connection,
            stream_id,
            status,
            body,
        )
        writer.write(outgoing)
        await writer.drain()

        while not complete:
            data = await reader.read(65_536)
            if not data:
                raise ConnectionError("the server closed before the response completed")

            connection.receive_data(data)
            status, complete = process_response_events(
                connection,
                stream_id,
                status,
                body,
            )

            outgoing = connection.data_to_send()
            # Serialization can itself produce FrameNotSent or StreamClosed.
            status, sent_complete = process_response_events(
                connection,
                stream_id,
                status,
                body,
            )
            complete = complete or sent_complete
            if outgoing:
                writer.write(outgoing)
                await writer.drain()

        if status is None:
            raise RuntimeError("the response ended without final headers")
        return status, bytes(body)
    finally:
        writer.close()
        # Some HTTP/2 servers send trailing application data while TLS is
        # closing. The completed response above is still valid.
        with suppress(ssl.SSLError):
            await writer.wait_closed()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch one HTTPS URL with ngh2")
    parser.add_argument("url", nargs="?", default="https://nghttp2.org/")
    args = parser.parse_args()

    status, body = await get(args.url)
    print(f"status: {status}")
    print(body.decode(errors="replace"))


if __name__ == "__main__":
    asyncio.run(main())
