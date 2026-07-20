from .enums import FrameType
from .exceptions import NGH2Error
from .types import Header

class Event:
    __match_args__ = ()

class RequestReceived(Event):
    __match_args__ = ("stream_id", "headers", "end_stream")

    def __init__(
        self,
        stream_id: int,
        headers: tuple[Header, ...],
        end_stream: bool,
    ) -> None: ...
    @property
    def stream_id(self) -> int: ...
    @property
    def headers(self) -> tuple[Header, ...]: ...
    @property
    def end_stream(self) -> bool: ...

class ResponseReceived(Event):
    __match_args__ = ("stream_id", "headers", "end_stream")

    def __init__(
        self,
        stream_id: int,
        headers: tuple[Header, ...],
        end_stream: bool,
    ) -> None: ...
    @property
    def stream_id(self) -> int: ...
    @property
    def headers(self) -> tuple[Header, ...]: ...
    @property
    def end_stream(self) -> bool: ...

class InformationalResponseReceived(Event):
    __match_args__ = ("stream_id", "headers")

    def __init__(self, stream_id: int, headers: tuple[Header, ...]) -> None: ...
    @property
    def stream_id(self) -> int: ...
    @property
    def headers(self) -> tuple[Header, ...]: ...

class TrailersReceived(Event):
    __match_args__ = ("stream_id", "headers")

    def __init__(self, stream_id: int, headers: tuple[Header, ...]) -> None: ...
    @property
    def stream_id(self) -> int: ...
    @property
    def headers(self) -> tuple[Header, ...]: ...

class PushedStreamReceived(Event):
    __match_args__ = ("stream_id", "promised_stream_id", "headers")

    def __init__(
        self,
        stream_id: int,
        promised_stream_id: int,
        headers: tuple[Header, ...],
    ) -> None: ...
    @property
    def stream_id(self) -> int: ...
    @property
    def promised_stream_id(self) -> int: ...
    @property
    def headers(self) -> tuple[Header, ...]: ...

class DataReceived(Event):
    __match_args__ = (
        "stream_id",
        "data",
        "end_stream",
    )

    def __init__(
        self,
        stream_id: int,
        data: bytes,
        end_stream: bool,
    ) -> None: ...
    @property
    def stream_id(self) -> int: ...
    @property
    def data(self) -> bytes: ...
    @property
    def end_stream(self) -> bool: ...

class StreamReset(Event):
    __match_args__ = ("stream_id", "error_code")

    def __init__(self, stream_id: int, error_code: int) -> None: ...
    @property
    def stream_id(self) -> int: ...
    @property
    def error_code(self) -> int: ...

class StreamClosed(Event):
    __match_args__ = ("stream_id", "error_code")

    def __init__(self, stream_id: int, error_code: int) -> None: ...
    @property
    def stream_id(self) -> int: ...
    @property
    def error_code(self) -> int: ...

class SettingsReceived(Event):
    __match_args__ = ("settings",)

    def __init__(self, settings: dict[int, int]) -> None: ...
    @property
    def settings(self) -> dict[int, int]: ...

class SettingsAcknowledged(Event):
    __match_args__ = ()

class PingReceived(Event):
    __match_args__ = ("opaque_data",)

    def __init__(self, opaque_data: bytes) -> None: ...
    @property
    def opaque_data(self) -> bytes: ...

class PingAcknowledged(Event):
    __match_args__ = ("opaque_data",)

    def __init__(self, opaque_data: bytes) -> None: ...
    @property
    def opaque_data(self) -> bytes: ...

class WindowUpdated(Event):
    __match_args__ = ("stream_id", "increment")

    def __init__(self, stream_id: int, increment: int) -> None: ...
    @property
    def stream_id(self) -> int: ...
    @property
    def increment(self) -> int: ...

class GoAwayReceived(Event):
    __match_args__ = ("last_stream_id", "error_code", "debug_data")

    def __init__(
        self,
        last_stream_id: int,
        error_code: int,
        debug_data: bytes,
    ) -> None: ...
    @property
    def last_stream_id(self) -> int: ...
    @property
    def error_code(self) -> int: ...
    @property
    def debug_data(self) -> bytes: ...

class AltSvcReceived(Event):
    __match_args__ = ("stream_id", "origin", "field_value")

    def __init__(self, stream_id: int, origin: bytes, field_value: bytes) -> None: ...
    @property
    def stream_id(self) -> int: ...
    @property
    def origin(self) -> bytes: ...
    @property
    def field_value(self) -> bytes: ...

class OriginReceived(Event):
    __match_args__ = ("origins",)

    def __init__(self, origins: tuple[bytes, ...]) -> None: ...
    @property
    def origins(self) -> tuple[bytes, ...]: ...

class PriorityUpdateReceived(Event):
    __match_args__ = ("prioritized_stream_id", "field_value")

    def __init__(self, prioritized_stream_id: int, field_value: bytes) -> None: ...
    @property
    def prioritized_stream_id(self) -> int: ...
    @property
    def field_value(self) -> bytes: ...

class FrameNotSent(Event):
    __match_args__ = ("stream_id", "frame_type", "error")

    def __init__(
        self,
        stream_id: int,
        frame_type: FrameType,
        error: NGH2Error,
    ) -> None: ...
    @property
    def stream_id(self) -> int: ...
    @property
    def frame_type(self) -> FrameType: ...
    @property
    def error(self) -> NGH2Error: ...
