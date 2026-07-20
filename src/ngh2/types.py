from dataclasses import dataclass
from typing import NamedTuple, TypeAlias


class NeverIndexedHeader(NamedTuple):
    """A header field that HPACK must encode as never indexed.

    Attributes:
        name: Header name as bytes.
        value: Header value as bytes.
    """

    name: bytes
    value: bytes


Header: TypeAlias = tuple[bytes, bytes] | NeverIndexedHeader


@dataclass(frozen=True, slots=True)
class Priority:
    """RFC 9218 extensible priority parameters.

    See RFC 9218, section 4:
    https://www.rfc-editor.org/rfc/rfc9218.html#section-4

    Attributes:
        urgency: Scheduling urgency from 0 (highest) through 7 (lowest).
            Values above 7 are treated as 7 when applied.
        incremental: Whether the response benefits from incremental delivery.
    """

    urgency: int = 3
    incremental: bool = False
