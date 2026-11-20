"""A failed approval is always dropped, including a memory add that was over the size limit (Kelly, 2026-11-13)."""

import os
import pathlib
import shutil
import tempfile

import pytest


@pytest.fixture
def hermes_home(monkeypatch):
    d = tempfile.mkdtemp(prefix="hermes_approve_overlimit_")
    home = os.path.join(d, ".hermes")
    os.makedirs(home)
    monkeypatch.setenv("HERMES_HOME", home)
    yield pathlib.Path(d)
    shutil.rmtree(d, ignore_errors=True)


def test_over_limit_memory_proposal_is_dropped_with_the_reason(hermes_home):
    from tools.memory_tool import MemoryStore
    from tools import write_approval as wa
    from hermes_cli import write_approval_commands as cmds
    store = MemoryStore(200, 100)
    store.load_from_disk()
    assert store.add("memory", "x" * 150)["success"] is True
    wa.stage_write(wa.MEMORY, {"action": "add", "target": "memory", "content": "y" * 120},
                   summary="add y", origin="foreground")
    out = cmds._approve(wa.MEMORY, ["all"], store)
    assert "exceed the limit" in out and "dropped from pending" in out
    assert wa.list_pending(wa.MEMORY) == []


def test_other_memory_rejection_is_dropped_too(hermes_home):
    from tools.memory_tool import MemoryStore
    from tools import write_approval as wa
    from hermes_cli import write_approval_commands as cmds
    store = MemoryStore(200, 100)
    store.load_from_disk()
    wa.stage_write(wa.MEMORY, {"action": "remove", "target": "memory", "old_text": "no such entry"},
                   summary="remove missing", origin="foreground")
    out = cmds._approve(wa.MEMORY, ["all"], store)
    assert "dropped from pending" in out
    assert wa.list_pending(wa.MEMORY) == []
