"""A broken skill BATCH (the shape the model really sends) is rejected before staging (Ari's live test, 2026-11-13)."""

import json
import os
import pathlib
import shutil
import tempfile
from unittest.mock import patch

import pytest

BODY = "---\nname: ok-skill\ndescription: A small test skill used only by the test suite.\n---\n# Ok\n\nSome body text.\n"


@pytest.fixture
def hermes_home(monkeypatch):
    d = tempfile.mkdtemp(prefix="hermes_batch_prestage_")
    home = os.path.join(d, ".hermes")
    os.makedirs(home)
    monkeypatch.setenv("HERMES_HOME", home)
    yield pathlib.Path(d)
    shutil.rmtree(d, ignore_errors=True)


def _gate_on(monkeypatch):
    from tools import write_approval as wa
    monkeypatch.setattr(wa, "write_approval_enabled", lambda subsystem: True)
    return wa


def _call(sm, ops):
    # the registered handler's entry point: the model sends an operations list
    return json.loads(sm._skill_manage_from({"operations": ops}))


@pytest.mark.parametrize("bad", ["../../etc", "a" * 300, "bad\x00name", "UPPER Case"])
def test_bad_create_name_is_rejected_not_staged(hermes_home, monkeypatch, bad):
    import tools.skill_manager_tool as sm
    wa = _gate_on(monkeypatch)
    skills = hermes_home / "skills"
    skills.mkdir()
    with patch.object(sm, "SKILLS_DIR", skills):
        out = _call(sm, [{"action": "create", "name": bad, "content": BODY}])
    assert out.get("success") is False
    assert out.get("staged") is not True
    assert "operations[0]" in out.get("error", "")
    assert wa.list_pending(wa.SKILLS) == []


def test_bad_new_skill_body_is_rejected_not_staged(hermes_home, monkeypatch):
    import tools.skill_manager_tool as sm
    wa = _gate_on(monkeypatch)
    skills = hermes_home / "skills"
    skills.mkdir()
    with patch.object(sm, "SKILLS_DIR", skills):
        out = _call(sm, [{"action": "create", "name": "ok-skill", "content": "no frontmatter here"}])
    assert out.get("success") is False and out.get("staged") is not True
    assert wa.list_pending(wa.SKILLS) == []


def test_second_op_bad_name_rejects_the_whole_batch(hermes_home, monkeypatch):
    import tools.skill_manager_tool as sm
    wa = _gate_on(monkeypatch)
    skills = hermes_home / "skills"
    skills.mkdir()
    with patch.object(sm, "SKILLS_DIR", skills):
        out = _call(sm, [{"action": "create", "name": "ok-skill", "content": BODY},
                         {"action": "create", "name": "../../etc", "content": BODY}])
    assert out.get("success") is False and "operations[1]" in out.get("error", "")
    assert wa.list_pending(wa.SKILLS) == []


def test_valid_batch_is_still_staged(hermes_home, monkeypatch):
    import tools.skill_manager_tool as sm
    wa = _gate_on(monkeypatch)
    skills = hermes_home / "skills"
    skills.mkdir()
    with patch.object(sm, "SKILLS_DIR", skills):
        out = _call(sm, [{"action": "create", "name": "ok-skill", "content": BODY}])
    assert out.get("success") is True and out.get("staged") is True
    assert len(wa.list_pending(wa.SKILLS)) == 1
