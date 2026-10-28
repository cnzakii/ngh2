---
description: Public Python API reference for ngh2 connections, configuration, events, and errors.
---

# Python API

The public package exposes one HTTP/2 connection type, immutable configuration
and event objects, protocol enums, and Python exceptions.

Methods queue protocol operations only. `data_to_send()` returns bytes for the
caller-owned transport, while `receive_data()` accepts bytes already read by
that transport.

Inputs documented as `bytes`, including event constructor arguments, also
accept `bytes` subclasses such as byte-valued enums; ngh2 uses their underlying
contents.

| If you need to… | Start with |
| --- | --- |
| initialize or drive a connection | `Connection.initiate_connection()`, `receive_data()`, `events()`, `data_to_send()` |
| send an HTTP message | `send_request()`, `send_response()`, `send_data()`, `send_trailers()` |
| react to peer activity | the event classes under **Events** |
| bound outbound body input | `queued_body_size()` and the [flow-control guide](guides/flow-control.md) |
| manage inbound flow control | `consume_received_data()` and `set_local_window_size()` |
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

`Header` is the public alias
`tuple[bytes, bytes] | NeverIndexedHeader`. Names and values are bytes;
pseudo-header fields must precede ordinary fields.

Header-taking methods accept an iterable of `Header` values, including lists,
tuples, generators, and `headers.items()`. Field order and repeated fields are
preserved.

The iterable is consumed during the method call, and the submitted values are
snapshotted. Changing an input container afterward does not change queued
fields, including trailers that will be sent after the body.

::: ngh2.NeverIndexedHeader

::: ngh2.Priority

::: ngh2.ErrorCode

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
        - ConnectionClosed
        - AltSvcReceived
        - OriginReceived
        - PriorityUpdateReceived

## Errors

::: ngh2.exceptions
