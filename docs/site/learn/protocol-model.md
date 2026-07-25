---
description: Understand how ngh2 maps HTTP/2 connections, streams, messages, frames, events, and caller-owned I/O.
---

# Understand the protocol model

You do not need to parse HTTP/2 frames to use ngh2, but you do need the right
boundaries in mind. Most integration mistakes come from confusing a connection
with a request, a frame with a message, or protocol flow control with
application backpressure.

## One connection contains many streams

One `Connection` represents one HTTP/2 connection and all of its shared state.
Each request and response exchange occupies a stream inside it.

```text
HTTP/2 connection
├── stream 1: request A ↔ response A
├── stream 3: request B ↔ response B
└── stream 5: request C ↔ response C
```

Client-initiated streams use increasing odd identifiers. Server-initiated push
streams use even identifiers. IDs are never reused on a connection.

The connection also carries shared control traffic such as SETTINGS, PING,
WINDOW_UPDATE, and GOAWAY.

## HTTP messages are assembled from frames

HTTP semantics stay familiar:

- a request starts with fields such as `:method`, `:scheme`, `:authority`, and
  `:path`;
- a final response starts with `:status`;
- either side can send body data and trailers; and
- a `1xx` response can precede the final response.

On the wire, HTTP/2 represents those messages with HEADERS, DATA, and other
frames. ngh2 parses, validates, compresses, schedules, and serializes them while
exposing message-level Python operations and event objects, so applications
rarely need to reason about individual frame boundaries.

One exception worth remembering is `DataReceived`: it represents one complete
DATA frame payload. A body can therefore arrive across several events.

## The connection is driven in both directions

```text
transport bytes → receive_data() → events() → application
transport bytes ← data_to_send() ← send_*() ← application
```

The arrows are deliberately separate. A successful `send_request()` or other
`send_*()` call means the local HTTP/2 state accepted that operation. It does
not mean the next `data_to_send()` call must contain all of its bytes, and it
does not mean anything was written to a socket. Scheduling, other streams, and
DATA flow-control windows determine when output becomes available.

`data_to_send()` advances that shared connection state and returns the bytes
currently ready for the caller-owned transport. If an accepted stream
operation later becomes impossible—for example, a queued push promise is
invalidated by new peer settings—the stream ends with a `StreamClosed` event
whose `local_error` explains the local failure. The connection and unrelated
streams can normally continue.

Likewise, `receive_data()` does not call your request handler. It updates the
connection and queues events for you to drain. Peer protocol violations may
also queue a reset or shutdown response, so drive `data_to_send()` after
handling input even when the application has nothing new to send.

## Ownership stays explicit

| ngh2 owns | Your application owns |
| --- | --- |
| connection and stream state | socket creation and closure |
| framing and HPACK | TLS, certificate checks, and ALPN |
| protocol validation | event loop, threads, and task scheduling |
| HTTP/2 flow-control windows | transport write buffering |
| outbound body queue and frame scheduling | body production limits, request routing, retries, and timeouts |
| protocol events | downstream body buffering and consumption |

One `Connection` must be driven by one thread or task at a time. Independent
connections can run concurrently; operations on the same connection must be
serialized in protocol order.

## Start HTTP/2 deliberately

For HTTPS, the transport negotiates the ALPN protocol `h2` before ngh2 sends its
connection preface. For cleartext deployments, HTTP/2 can start with prior
knowledge. The older HTTP/1.1 `h2c` Upgrade mechanism is deprecated and belongs
in compatibility code, not the default path.

These rules come from
[RFC 9113](https://www.rfc-editor.org/rfc/rfc9113.html); ngh2 does not replace
transport negotiation.

[Multiplex two streams →](multiplexing.md)
