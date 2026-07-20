import shutil
import subprocess
import sys
from pathlib import Path

import pytest

H2SPEC = shutil.which("h2spec")
SERVER = Path(__file__).parent / "interop" / "h2spec_server.py"


@pytest.mark.h2spec
@pytest.mark.skipif(H2SPEC is None, reason="h2spec executable is not installed")
def test_generic_h2spec_suite() -> None:
    assert H2SPEC is not None
    server = subprocess.Popen(
        [sys.executable, str(SERVER)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
    )
    assert server.stdout is not None

    try:
        port = server.stdout.readline().strip()
        assert port.isdecimal(), "h2spec adapter did not report its port"
        result = subprocess.run(
            [H2SPEC, "generic", "-h", "127.0.0.1", "-p", port],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    finally:
        server.terminate()
        _, server_errors = server.communicate(timeout=5)

    assert result.returncode == 0, result.stdout + server_errors
