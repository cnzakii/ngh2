---
description: Public Python API reference for ngh2 connections, configuration, events, and errors.
---

# Python API

The public package exposes one HTTP/2 connection type, immutable configuration
and event objects, protocol enums, and Python exceptions.

Methods queue protocol operations only. `data_to_send()` returns bytes for the
caller-owned transport, while `receive_data()` accepts bytes already read by
that transport.

| If you need to… | Start with |
| --- | --- |
| initialize or drive a connection | `Connection.initiate_connection()`, `receive_data()`, `events()`, `data_to_send()` |
| send an HTTP message | `send_request()`, `send_response()`, `send_data()`, `send_trailers()` |
| react to peer activity | the event classes under **Events** |
| control buffering | `pending_data()` and `acknowledge_received_data()` |
| shut down | `send_shutdown_notice()`, `send_goaway()`, `terminate_connection()` |
| use optional protocol controls | the [Advanced HTTP/2 guides](advanced.md) |
| tune limits | `Configuration` |

For lifecycle and recovery guidance, read
[Handle errors and shutdown](guides/errors-and-shutdown.md) before treating an
exception name as a retry decision.

## Connection

::: ngh2.Connection

## Configuration and roles

::: ngh2.Configuration

::: ngh2.Role

## Shared protocol types

::: ngh2.Priority

`Header` is the public alias
`tuple[bytes, bytes] | NeverIndexedHeader`. Header sequences preserve wire
order; pseudo-header fields precede ordinary fields.

::: ngh2.NeverIndexedHeader

::: ngh2.ErrorCode

::: ngh2.FrameType

::: ngh2.Setting

## h2c settings helper

::: ngh2.pack_settings_payload

## Events

::: ngh2.events
    options:
      members:
        - Event
        - RequestReceived
        - ResponseReceived
        - InformationalResponseReceived
        - TrailersReceived
        - PushedStreamReceived
        - DataReceived
        - StreamReset
        - StreamClosed
        - SettingsReceived
        - SettingsAcknowledged
        - PingReceived
        - PingAcknowledged
        - WindowUpdated
        - GoAwayReceived
        - AltSvcReceived
        - OriginReceived
        - PriorityUpdateReceived
        - FrameNotSent

## Errors

::: ngh2.exceptions
