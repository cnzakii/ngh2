---
description: Choose the ngh2 guide for SETTINGS, PING, server push, RFC 9218 priority, h2c, extended CONNECT, ALTSVC, and ORIGIN.
---

# Advanced HTTP/2

The common path needs messages, multiplexing, flow control, event handling, and
shutdown. Add the controls below only when the surrounding application has a
policy for the result.

## Follow the advanced path

| Need | Start here | Result |
| --- | --- | --- |
| inspect connection state, change SETTINGS, or measure liveness | [SETTINGS, PING, and connection state](advanced/settings-and-ping.md) | a complete control-frame round trip and a map of every query property |
| predict and deliver a resource before the client requests it | [Server push](advanced/server-push.md) | accepted and disabled push paths |
| reprioritize concurrent responses | [RFC 9218 priorities](advanced/priorities.md) | negotiated PRIORITY_UPDATE and server scheduling state |
| support legacy HTTP/1.1 Upgrade or extended CONNECT | [h2c and extended CONNECT](advanced/h2c-and-connect.md) | an upgraded stream and a negotiated tunnel request |
| advertise another service or a reusable origin set | [ALTSVC and ORIGIN](advanced/alternative-services.md) | received extension events and the policy boundary around them |

These features are independent. A client that needs h2c does not automatically
need server push or origin coalescing, and a server should not advertise an
extension it cannot apply safely.

[Start with SETTINGS and PING →](advanced/settings-and-ping.md)
