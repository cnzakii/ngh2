---
title: HTTP/2 user model
description: Normative protocol facts about connection startup, streams, messages, flow control, errors, shutdown, server push, extended CONNECT, priority, alternative services, and origin coalescing.
topics: [http2, streams, multiplexing, flow-control, errors, goaway, server-push, extended-connect, priority, alt-svc, origin]
checked_at: 2026-07-24
---

# HTTP/2 User Model

This document records protocol facts that user-facing explanations can rely
on. It does not define a Python API, documentation structure, or project
policy.

## Connections And Startup

**Normative source:** HTTP/2 is a connection-oriented application protocol.
Each request and response exchange uses a stream inside one connection, and
frames from different streams can be interleaved.

For an `https` URI, HTTP/2 is selected through TLS ALPN with the identifier
`h2`. Cleartext HTTP/2 can start with prior knowledge. The former HTTP/1.1
Upgrade mechanism identified by `h2c` is deprecated.

After the transport selects HTTP/2, both endpoints send a connection preface
that establishes the protocol and initial settings. The client preface begins
with a fixed 24-octet sequence followed by a SETTINGS frame; the server preface
begins with a SETTINGS frame.

Sources:

- [RFC 9113, section 2](https://www.rfc-editor.org/rfc/rfc9113.html#section-2)
- [RFC 9113, sections 3.1–3.4](https://www.rfc-editor.org/rfc/rfc9113.html#section-3)

## Streams, Messages, And Frames

**Normative source:** a stream is an independent, bidirectional sequence of
frames. Client-initiated streams use odd identifiers and server-initiated
streams use even identifiers. Stream identifiers increase monotonically and
cannot be reused.

One HTTP request/response exchange occupies one stream. An HTTP message is a
HEADERS frame followed by zero or more DATA frames and optional trailing
HEADERS. Informational responses can precede the final response. The frame
representation does not change HTTP method, status, field, or content
semantics.

Multiplexing permits multiple streams to make progress concurrently, but the
streams still share connection-level resources and state. Frames from separate
streams can be interleaved; frames within one header block remain contiguous.

Sources:

- [RFC 9113, section 5](https://www.rfc-editor.org/rfc/rfc9113.html#section-5)
- [RFC 9113, section 5.1.1](https://www.rfc-editor.org/rfc/rfc9113.html#section-5.1.1)
- [RFC 9113, section 8.1](https://www.rfc-editor.org/rfc/rfc9113.html#section-8.1)

## Flow Control

**Normative source:** flow control applies to DATA frames, not to header or
control frames. It operates independently at connection and stream scope.
Each receiver advertises how many body octets it is prepared to accept; a
sender cannot transmit DATA beyond either available window.

Only the receiver determines when to increase a window with WINDOW_UPDATE.
Endpoints cannot disable flow control, though a receiver can advertise a large
window. Implementations need to read and process frames even when they cannot
send DATA, because WINDOW_UPDATE and other control frames can unblock progress.
Poorly coordinated resource dependencies can deadlock a connection.

Protocol flow control limits bytes on the wire. It does not by itself limit
bytes already buffered by an application or waiting in a transport.

Source:
[RFC 9113, section 5.2](https://www.rfc-editor.org/rfc/rfc9113.html#section-5.2).

## Error Scope

**Normative source:** a connection error makes the entire HTTP/2 connection
unusable. The endpoint sends GOAWAY when possible and closes the transport. A
stream error affects one stream; the endpoint sends RST_STREAM and other
streams can continue.

The error codes carried by GOAWAY and RST_STREAM describe wire-level protocol
conditions. How a library exposes local misuse, peer violations, and transport
failures is an API decision rather than an HTTP/2 requirement.

Sources:

- [RFC 9113, section 5.4](https://www.rfc-editor.org/rfc/rfc9113.html#section-5.4)
- [RFC 9113, section 7](https://www.rfc-editor.org/rfc/rfc9113.html#section-7)

## GOAWAY And Request Reliability

**Normative source:** GOAWAY starts connection shutdown and identifies the
highest peer-initiated stream that might have been processed. New streams must
not be created after receiving GOAWAY. Streams with larger identifiers are
known not to have been processed and can be retried safely on a new connection;
the application still determines whether other requests are safe to retry.

A graceful server shutdown can first send GOAWAY with the largest possible
stream identifier, allow time for new stream creation to stop, and then send a
second GOAWAY with the last processed stream identifier. The specification
recommends allowing at least one round-trip time before the second frame.

Sources:

- [RFC 9113, section 6.8](https://www.rfc-editor.org/rfc/rfc9113.html#section-6.8)
- [RFC 9113, section 8.7](https://www.rfc-editor.org/rfc/rfc9113.html#section-8.7)

## Optional Features

**Normative source:** server push is optional and can be disabled by a client.
The server predicts a future request and sends a promised request plus its
response on a separate stream. The specification warns that incorrect
predictions waste bandwidth and can reduce performance.

Extended CONNECT is enabled by a server advertising
`SETTINGS_ENABLE_CONNECT_PROTOCOL=1`. A client must not send an extended CONNECT
request before receiving that setting. An extended CONNECT request carries
`:method` set to `CONNECT` plus `:protocol`, `:scheme`, `:path`, and
`:authority`; the protocol named by `:protocol` defines the resulting stream's
use.

RFC 9113 deprecates the original HTTP/2 dependency-tree priority scheme.
RFC 9218 defines extensible priority using an urgency from 0 through 7 and an
incremental flag. Priority signals are advisory and do not guarantee a
particular scheduling result.

An ALTSVC frame advertises another protocol, host, or port through which the
same origin may be reached. Clients may ignore an advertisement and must still
authenticate the alternative service for the original origin.

An ORIGIN frame lets a server describe the origins for which a TLS HTTP/2
connection can be authoritative. It is advisory input to connection coalescing,
does not remove certificate validation, and is ignored on `h2c` connections.

Sources:

- [RFC 9113, section 8.4](https://www.rfc-editor.org/rfc/rfc9113.html#section-8.4)
- [RFC 8441, sections 3–4](https://www.rfc-editor.org/rfc/rfc8441.html#section-3)
- [RFC 9218, section 4](https://www.rfc-editor.org/rfc/rfc9218.html#section-4)
- [RFC 9218, section 7](https://www.rfc-editor.org/rfc/rfc9218.html#section-7)
- [RFC 7838, sections 2.1 and 4](https://www.rfc-editor.org/rfc/rfc7838.html#section-2.1)
- [RFC 8336, sections 2.2 and 2.4](https://www.rfc-editor.org/rfc/rfc8336.html#section-2.2)
