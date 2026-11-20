"""Approve drops a record the applier rejected, keeps one that could not run (Kelly, 2026-11-13)."""

import os
import pathlib
import shutil
import tempfile
from unittest.mock import patch

import pytest

BODY = "---\nname: ok-skill\ndescription: y\n---\nbody"


@pytest.fixture
def hermes_home(monkeypatch):
    d = tempfile.mkdtemp(prefix="hermes_approve_drop_")
    home = os.path.join(d, ".hermes")
    os.makedirs(home)
    monkeypatch.setenv("HERMES_HOME", home)
    yield pathlib.Path(d)
    shutil.rmtree(d, ignore_errors=True)


def test_rejected_skill_record_is_dropped_with_reason(hermes_home):
    import tools.skill_manager_tool as sm
    from tools import write_approval as wa
    from hermes_cli import write_approval_commands as cmds
    skills = hermes_home / "skills"
    skills.mkdir()
    wa.stage_write(wa.SKILLS, {"action": "create", "name": "../../etc", "content": BODY},
                   summary="create ../../etc", origin="foreground")
    assert len(wa.list_pending(wa.SKILLS)) == 1
    with patch.object(sm, "SKILLS_DIR", skills):
        out = cmds._approve(wa.SKILLS, ["all"], None)
    assert "Invalid skill name" in out and "dropped from pending" in out
    assert "create ../../etc" in out
    assert wa.list_pending(wa.SKILLS) == []
    assert list(skills.rglob("*")) == []


def test_record_that_could_not_run_is_kept_for_retry(hermes_home):
    from tools import write_approval as wa
    from hermes_cli import write_approval_commands as cmds
    rec = wa.stage_write(wa.MEMORY, {"action": "add", "target": "memory", "content": "X"},
                         summary="add X", origin="foreground")
    out = cmds._approve(wa.MEMORY, ["all"], None)   # no memory store: the applier cannot run
    assert "memory store unavailable" in out and "kept pending" in out
    assert [r["id"] for r in wa.list_pending(wa.MEMORY)] == [rec["id"]]
