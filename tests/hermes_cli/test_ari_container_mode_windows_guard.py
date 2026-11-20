"""Windows container-mode guard (Ari port Step 2, from Reed's S10 hunk).

NixOS container mode reads a backend name from HERMES_HOME/.container-mode and execs into it. On Windows a
writable file must never be able to name a backend that gets executed, so get_container_exec_info() returns None
there even when the file exists and says container mode is on.
"""
import os

import pytest


@pytest.fixture
def container_file(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.delenv("HERMES_DEV", raising=False)
    (home / ".container-mode").write_text(
        "backend=evil-backend\ncontainer_name=x\nexec_user=root\nhermes_bin=/bin/sh\n", encoding="utf-8")
    return home


@pytest.mark.skipif(os.name != "nt", reason="the guard is Windows-only")
def test_windows_ignores_container_mode_file(container_file):
    from hermes_cli.config import get_container_exec_info
    assert get_container_exec_info() is None


@pytest.mark.skipif(os.name != "nt", reason="the guard is Windows-only")
def test_windows_no_file_still_none(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.delenv("HERMES_DEV", raising=False)
    from hermes_cli.config import get_container_exec_info
    assert get_container_exec_info() is None
