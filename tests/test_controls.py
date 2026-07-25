from typing import cast

import pytest

from ngh2 import (
    AltSvcReceived,
    Configuration,
    Connection,
    ErrorCode,
    GoAwayReceived,
    OriginReceived,
    PingAcknowledged,
    PingReceived,
    Priority,
    PriorityUpdateReceived,
    PushDisabledError,
    ResponseReceived,
    Role,
    Setting,
    SettingsAcknowledged,
    SettingsReceived,
    StreamClosed,
    StreamReset,
    StreamUnavailableError,
    WindowUpdated,
    pack_settings_payload,
)


def handshake() -> tuple[Connection, Connection]:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    client.initiate_connection({Setting.MAX_CONCURRENT_STREAMS: 10})
    server.initiate_connection()
    server.receive_data(client.data_to_send())
    client.receive_data(server.data_to_send())
    server.receive_data(client.data_to_send())
    client.receive_data(server.data_to_send())
    client.events()
    server.events()
    return client, server


class TestControlFrames:
    def test_settings_payload_uses_http2_settings_wire_format(self):
        payload = pack_settings_payload({Setting.MAX_FRAME_SIZE: 32_768})

        assert payload == b"\x00\x05\x00\x00\x80\x00"

    def test_settings_payload_rejects_non_mapping_input(self):
        with pytest.raises(TypeError, match="settings must be a mapping"):
            pack_settings_payload(cast(dict[int, int], []))

    def test_wire_integer_arguments_reject_fractional_values(self):
        with pytest.raises(TypeError):
            pack_settings_payload({Setting.MAX_FRAME_SIZE: cast(int, 1.5)})

        server = Connection(Role.SERVER)
        server.initiate_connection()
        with pytest.raises(TypeError):
            server.data_to_send(cast(int, 1.5))
        with pytest.raises(TypeError):
            server.send_goaway(cast(int, 1.5))
        with pytest.raises(TypeError):
            server.send_alt_svc(b'h3=":443"', stream_id=cast(int, 1.5))

    def test_h2c_upgrade_uses_binary_settings_payload(self):
        settings = {Setting.MAX_CONCURRENT_STREAMS: 10}
        payload = pack_settings_payload(settings)
        client = Connection(Role.CLIENT)
        server = Connection(Role.SERVER)

        client.initiate_upgrade(payload)
        server.initiate_upgrade(payload)
        server.receive_data(client.data_to_send())
        client.receive_data(server.data_to_send())
        client.events()
        server.events()

        server.send_response(1, [(b":status", b"204")], end_stream=True)
        client.receive_data(server.data_to_send())
        events = client.events()
        assert any(isinstance(event, ResponseReceived) for event in events)
        assert any(isinstance(event, StreamClosed) for event in events)

    def test_h2c_upgrade_preserves_callback_errors(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        def fail_settings_event(_: dict[int, int]) -> SettingsReceived:
            raise MemoryError("settings event allocation failed")

        monkeypatch.setattr("ngh2._core.SettingsReceived", fail_settings_event)
        server = Connection(Role.SERVER)
        payload = pack_settings_payload({Setting.MAX_CONCURRENT_STREAMS: 10})

        with pytest.raises(MemoryError, match="settings event allocation failed"):
            server.initiate_upgrade(payload)

    def test_h2c_upgrade_rejects_too_many_settings_as_invalid_input(self):
        server = Connection(Role.SERVER, Configuration(max_settings=1))
        payload = pack_settings_payload(
            {
                Setting.MAX_CONCURRENT_STREAMS: 10,
                Setting.MAX_FRAME_SIZE: 32_768,
            }
        )

        with pytest.raises(ValueError):
            server.initiate_upgrade(payload)

        server.initiate_upgrade(
            pack_settings_payload({Setting.MAX_CONCURRENT_STREAMS: 10})
        )

    def test_settings_ping_reset_and_goaway_events(self):
        client, server = handshake()

        client.update_settings({Setting.MAX_FRAME_SIZE: 32_768})
        client.ping(b"12345678")
        server.receive_data(client.data_to_send())
        received = server.events()
        assert any(isinstance(item, SettingsReceived) for item in received)
        assert (
            next(
                item for item in received if isinstance(item, PingReceived)
            ).opaque_data
            == b"12345678"
        )

        client.receive_data(server.data_to_send())
        acknowledgements = client.events()
        assert any(isinstance(item, SettingsAcknowledged) for item in acknowledgements)
        assert (
            next(
                item for item in acknowledgements if isinstance(item, PingAcknowledged)
            ).opaque_data
            == b"12345678"
        )

        stream_id = client.send_request(
            [
                (b":method", b"GET"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/"),
            ],
            end_stream=True,
        )
        server.receive_data(client.data_to_send())
        server.events()
        server.reset_stream(stream_id, ErrorCode.CANCEL)
        client.receive_data(server.data_to_send())
        reset = next(item for item in client.events() if isinstance(item, StreamReset))
        assert reset.error_code == ErrorCode.CANCEL

        server.send_goaway(
            ErrorCode.NO_ERROR,
            last_stream_id=stream_id,
            debug_data=b"done",
        )
        client.receive_data(server.data_to_send())
        goaway = next(
            item for item in client.events() if isinstance(item, GoAwayReceived)
        )
        assert goaway.last_stream_id == stream_id
        assert goaway.debug_data == b"done"

    def test_settings_event_owns_a_read_only_snapshot(self):
        source: dict[int, int] = {int(Setting.MAX_FRAME_SIZE): 32_768}
        event = SettingsReceived(source)

        source[Setting.MAX_FRAME_SIZE] = 65_535

        assert event.settings[Setting.MAX_FRAME_SIZE] == 32_768
        mutable = cast(dict[int, int], event.settings)
        with pytest.raises(TypeError):
            mutable[Setting.MAX_FRAME_SIZE] = 16_384

    def test_query_surface_exposes_native_state(self):
        client, _ = handshake()

        assert client.want_read
        assert client.can_send_request
        assert client.next_stream_id == 1
        assert client.remote_window_size > 0
        assert client.local_window_size > 0
        assert client.remote_settings[Setting.MAX_FRAME_SIZE] == 16_384

        with pytest.raises(StreamUnavailableError):
            client.stream_remote_window_size(99)
        with pytest.raises(StreamUnavailableError):
            client.stream_local_window_size(99)

    def test_set_local_window_size_updates_connection_and_stream_capacity(self):
        client, server = handshake()
        stream_id = client.send_request(
            [
                (b":method", b"POST"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/"),
            ],
        )
        server.receive_data(client.data_to_send())
        server.events()

        server.set_local_window_size(100_000)
        server.set_local_window_size(90_000, stream_id=stream_id)
        client.receive_data(server.data_to_send())

        updates = [
            event for event in client.events() if isinstance(event, WindowUpdated)
        ]
        assert {(event.stream_id, event.increment) for event in updates} == {
            (0, 34_465),
            (stream_id, 24_465),
        }
        assert server.local_window_size == 100_000
        assert server.stream_local_window_size(stream_id) == 90_000

        with pytest.raises(StreamUnavailableError):
            server.set_local_window_size(1, stream_id=99)
        with pytest.raises(TypeError):
            server.set_local_window_size(cast(int, 1.5))
        with pytest.raises(TypeError):
            server.set_local_window_size(1, stream_id=cast(int, 1.5))
        with pytest.raises(TypeError):
            server.set_local_window_size(1, stream_id=cast(int, 0.0))
        with pytest.raises(ValueError):
            server.set_local_window_size(1 << 31)

    def test_invalid_upgrade_settings_do_not_initiate_the_connection(self):
        server = Connection(Role.SERVER)

        with pytest.raises(TypeError):
            server.initiate_upgrade(
                b"",
                local_settings=cast(dict[int, int], {"invalid": 1}),
            )

        server.initiate_connection()
        assert server.data_to_send()

    @pytest.mark.parametrize(
        "method",
        ["send_response", "send_informational_response"],
    )
    def test_responses_reject_unknown_streams_immediately(self, method):
        server = Connection(Role.SERVER)
        server.initiate_connection()

        with pytest.raises(StreamUnavailableError):
            getattr(server, method)(99, [(b":status", b"200")])

        assert server.queued_body_size() == 0

    def test_builtin_extension_frames_are_exposed_as_events(self):
        client, server = handshake()

        server.send_alt_svc(b'h3=":443"', origin=b"https://example.test")
        server.send_origins([b"https://example.test", b"https://cdn.example.test"])
        client.receive_data(server.data_to_send())

        events = client.events()
        alt_svc = next(item for item in events if isinstance(item, AltSvcReceived))
        origins = next(item for item in events if isinstance(item, OriginReceived))
        assert alt_svc.origin == b"https://example.test"
        assert alt_svc.field_value == b'h3=":443"'
        assert origins.origins == (
            b"https://example.test",
            b"https://cdn.example.test",
        )

        with pytest.raises(TypeError):
            server.send_origins(cast(list[bytes], [3]))

    def test_delayed_frame_failure_is_an_event(self):
        client, server = handshake()
        client.update_settings({Setting.ENABLE_PUSH: 0})
        server.receive_data(client.data_to_send())
        client.receive_data(server.data_to_send())
        client.events()
        server.events()
        stream_id = client.send_request(
            [
                (b":method", b"GET"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/"),
            ],
            end_stream=True,
        )
        server.receive_data(client.data_to_send())
        server.events()

        promised_stream_id = server.send_push_promise(
            stream_id,
            [
                (b":method", b"GET"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/asset"),
            ],
        )
        server.data_to_send()

        closed = next(
            item for item in server.events() if isinstance(item, StreamClosed)
        )
        assert closed.stream_id == promised_stream_id
        assert closed.error_code == ErrorCode.INTERNAL_ERROR
        assert isinstance(closed.local_error, PushDisabledError)

    def test_extensible_priority_round_trip(self):
        client = Connection(Role.CLIENT)
        server = Connection(Role.SERVER)
        settings = {Setting.NO_RFC7540_PRIORITIES: 1}
        client.initiate_connection(settings)
        server.initiate_connection(settings)
        server.receive_data(client.data_to_send())
        client.receive_data(server.data_to_send())
        server.receive_data(client.data_to_send())
        client.receive_data(server.data_to_send())
        client.events()
        server.events()
        stream_id = client.send_request(
            [
                (b":method", b"GET"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/"),
            ],
            end_stream=True,
        )
        server.receive_data(client.data_to_send())
        server.events()

        assert client.send_priority_update(stream_id, b"u=1, i")
        server.receive_data(client.data_to_send())
        update = next(
            item for item in server.events() if isinstance(item, PriorityUpdateReceived)
        )
        assert update.field_value == b"u=1, i"
        assert server.set_stream_priority(stream_id, Priority(2, True))
        assert server.get_stream_priority(stream_id) == Priority(2, True)

    def test_extensible_priority_before_settings_acknowledgement(self):
        client = Connection(Role.CLIENT)
        server = Connection(Role.SERVER)
        client.initiate_connection()
        server.initiate_connection({Setting.NO_RFC7540_PRIORITIES: 1})
        stream_id = client.send_request(
            [
                (b":method", b"GET"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/"),
            ],
            end_stream=True,
        )

        assert client.local_settings[Setting.NO_RFC7540_PRIORITIES] == 0xFFFFFFFF
        assert client.remote_settings[Setting.NO_RFC7540_PRIORITIES] == 0xFFFFFFFF
        assert client.send_priority_update(stream_id, b"u=1")

        server.receive_data(client.data_to_send())
        server.events()
        assert server.set_stream_priority(stream_id, Priority(2))
        assert server.get_stream_priority(stream_id) == Priority(2)
