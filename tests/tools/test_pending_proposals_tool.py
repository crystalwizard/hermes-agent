"""pending_proposals: visibility and deliberate action on staged writes (2026-11-13)."""

import json
import os
import shutil
import tempfile
from types import SimpleNamespace

import pytest


@pytest.fixture
def hermes_home(monkeypatch):
    d = tempfile.mkdtemp(prefix="hermes_pp_")
    home = os.path.join(d, ".hermes")
    os.makedirs(home)
    monkeypatch.setenv("HERMES_HOME", home)
    yield home
    shutil.rmtree(d, ignore_errors=True)


def _stage(wa, name="sk", origin="background_review", subsystem=None):
    subsystem = subsystem or wa.SKILLS
    payload = {"action": "batch", "operations": [{"action": "create", "name": name, "content": "BODY " * 400}]}
    return wa.stage_write(subsystem, payload, summary=f"batch(1 ops: create) on {name}", origin=origin)


def _call(args):
    from tools.pending_proposals_tool import pending_proposals
    return json.loads(pending_proposals(args))


def test_list_and_read(hermes_home):
    from tools import write_approval as wa
    r = _stage(wa)
    out = _call({"action": "list"})
    assert out["success"] and out["count"] == 1 and out["pending"][0]["id"] == r["id"]
    assert out["pending"][0]["origin"] == "background_review"
    rd = _call({"action": "read", "id": r["id"]})
    assert rd["success"] and rd["operations"][0]["name"] == "sk" and rd["operations"][0]["text_chars"] == 2000
    assert rd["operations"][0]["text_preview"].endswith("...[cut]")


def test_reject_needs_reason_discards_one_and_logs(hermes_home):
    from tools import write_approval as wa
    a, b = _stage(wa, "a"), _stage(wa, "b")
    assert _call({"action": "reject", "id": a["id"]})["success"] is False       # no reason
    assert len(wa.list_pending(wa.SKILLS)) == 2
    ok = _call({"action": "reject", "id": a["id"], "reason": "stale, superseded"})
    assert ok["success"] and ok["rejected"] == a["id"]
    assert [r["id"] for r in wa.list_pending(wa.SKILLS)] == [b["id"]]
    log = open(os.path.join(hermes_home, "pending", "decisions.jsonl"), encoding="utf-8").read()
    assert a["id"] in log and "stale, superseded" in log


def test_ask_approval_marks_record_and_shows_in_pending_list(hermes_home):
    from tools import write_approval as wa
    from hermes_cli import write_approval_commands as cmds
    r = _stage(wa)
    assert _call({"action": "ask_approval", "id": r["id"]})["success"] is False  # no note
    assert _call({"action": "ask_approval", "id": r["id"], "note": "this one is worth keeping"})["success"]
    assert wa.get_approval_request(wa.SKILLS, wa.get_pending(wa.SKILLS, r["id"]))["note"] == "this one is worth keeping"
    assert "asks for your approval: this one is worth keeping" in cmds._fmt_pending_list(wa.SKILLS)
    assert len(wa.list_pending(wa.SKILLS)) == 1                                    # still pending, not applied


def test_there_is_no_approve_action_and_bad_ids_do_not_crash(hermes_home):
    from tools import write_approval as wa
    r = _stage(wa)
    assert _call({"action": "approve", "id": r["id"]})["success"] is False
    assert _call({"action": "read", "id": "../x"})["success"] is False
    assert _call({"action": "reject", "id": "zzzzzzzz", "reason": "nothing there"})["success"] is False
    assert len(wa.list_pending(wa.SKILLS)) == 1


def test_refused_inside_unattended_review(hermes_home, monkeypatch):
    from tools import write_approval as wa
    import tools.skill_provenance as sp
    r = _stage(wa)
    monkeypatch.setattr(sp, "is_unattended_review", lambda: True)
    assert _call({"action": "reject", "id": r["id"], "reason": "should not work"})["success"] is False
    assert len(wa.list_pending(wa.SKILLS)) == 1


def test_gate_staged_proposal_is_announced():
    from agent.background_review import _action_lines
    lines = _action_lines({"success": True, "staged": True, "pending_id": "abcdef12", "gist": "create foo"}, {}, False)
    assert lines and "abcdef12" in lines[0] and "waiting for approval" in lines[0]


def test_session_start_notice(hermes_home):
    from tools import write_approval as wa
    from agent.system_prompt import _pending_proposals_part
    exposed = SimpleNamespace(valid_tool_names={"pending_proposals"})
    assert _pending_proposals_part(exposed) == []                                  # nothing pending
    _stage(wa)
    _stage(wa, "other", origin="foreground")
    part = _pending_proposals_part(exposed)
    assert len(part) == 1 and "2 write(s)" in part[0] and "1 came from your own background review" in part[0]
    assert _pending_proposals_part(SimpleNamespace(valid_tool_names=set())) == []  # tool not exposed: no notice


def test_review_fork_does_not_get_the_tool():
    from agent.background_review import _review_tool_whitelist
    wl, _extra = _review_tool_whitelist(SimpleNamespace(_memory_enabled=False, _user_profile_enabled=False), {}, False)
    assert "skill_manage" in wl and "pending_proposals" not in wl


def test_tool_is_in_the_toolsets():
    import toolsets
    assert "pending_proposals" in toolsets._HERMES_CORE_TOOLS
    assert "pending_proposals" in toolsets.TOOLSETS["skills"]["tools"]
