from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("DOTFILES_SANDBOX") != "1", reason="needs the disposable Docker container"
)


def test_container_uses_an_unprivileged_user_and_read_only_root() -> None:
    assert os.getuid() == 10001
    assert os.statvfs("/").f_flag & os.ST_RDONLY
    status = Path("/proc/self/status").read_text()
    assert "NoNewPrivs:\t1" in status
    assert "CapEff:\t0000000000000000" in status
    assert Path.home() == Path("/work/home")
    assert not Path("/var/run/docker.sock").exists()
    assert "SSH_AUTH_SOCK" not in os.environ
    assert "GITHUB_TOKEN" not in os.environ
    assert "OPENAI_API_KEY" not in os.environ
    assert not Path("/run/secrets/proxy_ca").exists()
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        assert not os.environ.get(name)
        assert not os.environ.get(name.lower())


def test_container_has_no_outbound_route() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(1)
        assert connection.connect_ex(("1.1.1.1", 443)) != 0
    routes = Path("/proc/net/route").read_text().splitlines()
    assert len(routes) == 1


def test_container_source_uses_a_fresh_local_index() -> None:
    result = subprocess.run(["git", "remote"], capture_output=True, text=True, check=True)
    assert result.stdout == ""
    assert not Path(".dotfiles.git").exists()
    assert Path(".git/index").is_file()
    assert Path("/work/src").stat().st_uid == 10001
