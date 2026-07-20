import sys
import sysconfig
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version
from typing import cast

import pytest

import ngh2
from ngh2 import (
    Configuration,
    Connection,
    ConnectionStateError,
    NGH2Error,
    RequestReceived,
    Role,
    __version__,
)


def test_free_threaded_import_keeps_the_gil_disabled() -> None:
    if not sysconfig.get_config_var("Py_GIL_DISABLED"):
        pytest.skip("requires a free-threaded CPython build")

    assert not sys.__dict__["_is_gil_enabled"]()


def test_free_threaded_connections_run_independently() -> None:
    if not sysconfig.get_config_var("Py_GIL_DISABLED"):
        pytest.skip("requires a free-threaded CPython build")

    def build_request(_: int) -> bytes:
        connection = Connection(Role.CLIENT)
        connection.initiate_connection()
        connection.send_request(
            [
                (b":method", b"GET"),
                (b":scheme", b"https"),
                (b":authority", b"example.com"),
                (b":path", b"/"),
            ],
            end_stream=True,
        )
        return connection.data_to_send()

    with ThreadPoolExecutor(max_workers=4) as executor:
        output = list(executor.map(build_request, range(64)))

    assert all(output)


class TestCore:
    def test_public_exports_are_unique_and_resolvable(self):
        assert len(ngh2.__all__) == len(set(ngh2.__all__))
        assert all(hasattr(ngh2, name) for name in ngh2.__all__)

    def test_package_version_matches_distribution_metadata(self):
        assert __version__ == version("ngh2")

    def test_connection_uses_default_configuration(self):
        connection = Connection(Role.CLIENT)

        assert connection.role is Role.CLIENT
        assert connection.config == Configuration(
            auto_window_update=True,
            peer_max_concurrent_streams=100,
            max_reserved_remote_streams=200,
            max_send_header_block_length=65_536,
            max_deflate_dynamic_table_size=4_096,
            max_outbound_ack=1_000,
            max_settings=32,
            stream_reset_rate_limit=(1_000, 33),
            max_continuations=8,
            glitch_rate_limit=(10_000, 330),
        )

    def test_connection_preserves_configuration(self):
        configuration = Configuration(auto_window_update=False)

        connection = Connection(Role.SERVER, configuration)

        assert connection.role is Role.SERVER
        assert connection.config is configuration

    def test_configuration_accepts_zero_native_limits(self):
        configuration = Configuration(
            peer_max_concurrent_streams=0,
            max_deflate_dynamic_table_size=0,
        )

        connection = Connection(Role.CLIENT, configuration)

        assert connection.config is configuration

    @pytest.mark.parametrize(
        "configuration",
        [
            Configuration(peer_max_concurrent_streams=-1),
            Configuration(peer_max_concurrent_streams=1 << 32),
            Configuration(max_settings=-1),
            Configuration(stream_reset_rate_limit=(1 << 64, 1)),
        ],
        ids=[
            "negative-u32",
            "overflow-u32",
            "negative-settings-limit",
            "overflow-u64",
        ],
    )
    def test_connection_rejects_native_option_overflow(self, configuration):
        with pytest.raises(OverflowError):
            Connection(Role.CLIENT, configuration)

    @pytest.mark.parametrize(
        ("name", "configuration"),
        [
            (
                "max_inbound_header_list_size",
                Configuration(max_inbound_header_list_size=-1),
            ),
            (
                "max_inbound_header_count",
                Configuration(max_inbound_header_count=-1),
            ),
        ],
        ids=["header-list-size", "header-count"],
    )
    def test_connection_rejects_negative_binding_limits(self, name, configuration):
        with pytest.raises(ValueError, match=f"{name} must be non-negative"):
            Connection(Role.CLIENT, configuration)

    def test_connection_rejects_invalid_constructor_arguments(self):
        with pytest.raises(TypeError, match="role must be a Role"):
            Connection(cast(Role, "client"))

        with pytest.raises(TypeError, match="config must be a Configuration"):
            Connection(Role.CLIENT, cast(Configuration, object()))

    def test_connection_rejects_reinitialization(self):
        connection = Connection(Role.CLIENT)

        with pytest.raises(ConnectionStateError, match="already initialized"):
            connection.__init__(Role.SERVER)

    def test_connection_state_errors_share_the_package_base(self):
        connection = Connection(Role.CLIENT)

        with pytest.raises(NGH2Error):
            connection.receive_data(b"")

    def test_events_are_read_only_and_support_class_patterns(self):
        event = RequestReceived(1, ((b":method", b"GET"),), True)

        match event:
            case RequestReceived(
                stream_id=stream_id,
                headers=headers,
                end_stream=True,
            ):
                pass
            case _:
                pytest.fail("request event did not match its public fields")

        assert stream_id == 1
        assert headers == ((b":method", b"GET"),)
        with pytest.raises(AttributeError):
            object.__setattr__(event, "stream_id", 3)

    def test_data_to_send_respects_amount(self):
        connection = Connection(Role.CLIENT)
        connection.initiate_connection()
        client_preface = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n"

        assert connection.data_to_send(0) == b""
        assert connection.data_to_send(5) == client_preface[:5]
        remainder = connection.data_to_send()
        assert remainder.startswith(client_preface[5:])
        assert len(remainder) == len(client_preface) - 5 + 9
        assert connection.data_to_send() == b""

    def test_data_to_send_rejects_negative_amount(self):
        connection = Connection(Role.SERVER)

        with pytest.raises(ValueError, match="amount must be non-negative"):
            connection.data_to_send(-1)
