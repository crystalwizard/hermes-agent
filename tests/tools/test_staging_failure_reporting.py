"""A change that could not be staged must be reported as NOT staged (Morrow, 2026-11-13)."""

import json
import os
import shutil
import tempfile
from types import SimpleNamespace

import pytest


@pytest.fixture
def hermes_home(monkeypatch):
    d = tempfile.mkdtemp(prefix="hermes_wa_unstaged_")
    home = os.path.join(d, ".hermes")
    os.makedirs(home)
    monkeypatch.setenv("HERMES_HOME", home)
    yield home
    shutil.rmtree(d, ignore_errors=True)


def _force_staging(monkeypatch, wa, record_id):
    monkeypatch.setattr(wa, "evaluate_gate",
                        lambda *a, **k: SimpleNamespace(allow=False, blocked=False, message="needs approval"))
    monkeypatch.setattr(wa, "stage_write",
                        lambda *a, **k: {"id": record_id, "summary": "s", "payload": {}})


def _not_staged(out):
    data = json.loads(out)
    return data.get("success") is not True and data.get("staged") is not True


def test_stage_write_failure_returns_unstaged_and_leaves_no_stray_file(hermes_home, monkeypatch):
    from tools import write_approval as wa

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(wa, "atomic_json_write", boom)
    rec = wa.stage_write(wa.MEMORY, {"action": "add", "content": "X"}, summary="x", origin="foreground")
    assert rec["id"] == "unstaged"
    assert wa.list_pending(wa.MEMORY) == []
    assert not [p for p in wa._pending_files(wa.MEMORY)]


def test_memory_gate_reports_failure_when_unstaged(hermes_home, monkeypatch):
    from tools import write_approval as wa
    from tools.memory_tool import _gate_or_stage
    _force_staging(monkeypatch, wa, "unstaged")
    assert _not_staged(_gate_or_stage("add to memory", "x", {"action": "add"}))


def test_memory_gate_still_reports_success_when_staged(hermes_home, monkeypatch):
    from tools import write_approval as wa
    from tools.memory_tool import _gate_or_stage
    _force_staging(monkeypatch, wa, "abcdef12")
    data = json.loads(_gate_or_stage("add to memory", "x", {"action": "add"}))
    assert data["success"] is True and data["staged"] is True and data["pending_id"] == "abcdef12"


def test_skill_gate_reports_failure_when_unstaged(hermes_home, monkeypatch):
    from tools import write_approval as wa
    from tools.skill_manager_tool import _run_write_gate
    _force_staging(monkeypatch, wa, "unstaged")
    assert _not_staged(_run_write_gate(lambda w: ({"action": "x"}, "gist")))


def test_skill_gate_still_reports_success_when_staged(hermes_home, monkeypatch):
    from tools import write_approval as wa
    from tools.skill_manager_tool import _run_write_gate
    _force_staging(monkeypatch, wa, "abcdef12")
    data = json.loads(_run_write_gate(lambda w: ({"action": "x"}, "gist")))
    assert data["success"] is True and data["staged"] is True


def test_background_gate_denies_plainly_when_unstaged(hermes_home, monkeypatch):
    from tools import write_approval as wa
    import tools.skill_provenance as sp
    from tools.memory_tool import _background_delete_gate
    monkeypatch.setattr(sp, "is_unattended_review", lambda: True)
    _force_staging(monkeypatch, wa, "unstaged")
    out = _background_delete_gate("remove", None, target="memory", old_text="x")
    assert out is not None and _not_staged(out)
