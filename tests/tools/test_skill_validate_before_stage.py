"""A broken skill write is rejected before staging, never staged-then-failed (Kelly, 2026-11-13)."""

import json
import os
import pathlib
import shutil
import tempfile
from unittest.mock import patch

import pytest

BODY = "---\nname: ok-skill\ndescription: y\n---\nbody"


@pytest.fixture
def hermes_home(monkeypatch):
    d = tempfile.mkdtemp(prefix="hermes_skill_prestage_")
    home = os.path.join(d, ".hermes")
    os.makedirs(home)
    monkeypatch.setenv("HERMES_HOME", home)
    yield pathlib.Path(d)
    shutil.rmtree(d, ignore_errors=True)


def _gate_on(monkeypatch):
    from tools import write_approval as wa
    monkeypatch.setattr(wa, "write_approval_enabled", lambda subsystem: True)
    return wa


@pytest.mark.parametrize("bad", ["../../etc", "a" * 300, "bad\x00name", ""])
def test_bad_name_is_rejected_not_staged(hermes_home, monkeypatch, bad):
    import tools.skill_manager_tool as sm
    wa = _gate_on(monkeypatch)
    skills = hermes_home / "skills"
    skills.mkdir()
    with patch.object(sm, "SKILLS_DIR", skills):
        out = json.loads(sm.skill_manage(action="create", name=bad, content=BODY))
    assert out.get("success") is False
    assert out.get("staged") is not True
    assert wa.list_pending(wa.SKILLS) == []


def test_malformed_patch_is_rejected_not_staged(hermes_home, monkeypatch):
    import tools.skill_manager_tool as sm
    wa = _gate_on(monkeypatch)
    skills = hermes_home / "skills"
    skills.mkdir()
    with patch.object(sm, "SKILLS_DIR", skills):
        out = json.loads(sm.skill_manage(action="patch", name="my-skill", old_string=None, new_string="x"))
    assert out.get("success") is False
    assert wa.list_pending(wa.SKILLS) == []


def test_valid_create_is_still_staged(hermes_home, monkeypatch):
    import tools.skill_manager_tool as sm
    wa = _gate_on(monkeypatch)
    skills = hermes_home / "skills"
    skills.mkdir()
    with patch.object(sm, "SKILLS_DIR", skills):
        out = json.loads(sm.skill_manage(action="create", name="ok-skill", content=BODY))
    assert out.get("success") is True and out.get("staged") is True
    assert len(wa.list_pending(wa.SKILLS)) == 1
