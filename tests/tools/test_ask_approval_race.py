"""ask_approval must never recreate a removed proposal (Morrow's v7 review, 2026-11-13)."""

import json
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def hermes_home(monkeypatch):
    d = tempfile.mkdtemp(prefix="hermes_ask_race_")
    home = os.path.join(d, ".hermes")
    os.makedirs(home)
    monkeypatch.setenv("HERMES_HOME", home)
    yield home
    shutil.rmtree(d, ignore_errors=True)


def _stage(wa):
    return wa.stage_write(wa.SKILLS, {"action": "batch", "operations": [{"action": "create", "name": "sk", "content": "B"}]},
                          summary="batch(1 ops: create) on sk", origin="background_review")


def _call(args):
    from tools.pending_proposals_tool import pending_proposals
    return json.loads(pending_proposals(args))


def test_removal_between_read_and_write_does_not_recreate_the_record(hermes_home, monkeypatch):
    from tools import write_approval as wa
    r = _stage(wa)
    real_get = wa.get_pending

    def get_then_user_rejects(sub, pid):
        rec = real_get(sub, pid)
        wa.discard_pending(sub, pid)          # the user approves/rejects right after the agent read it
        return rec

    monkeypatch.setattr(wa, "get_pending", get_then_user_rejects)
    out = _call({"action": "ask_approval", "id": r["id"], "note": "worth keeping"})
    monkeypatch.setattr(wa, "get_pending", real_get)
    assert out["success"] is False and "gone" in out["error"]
    assert wa.list_pending(wa.SKILLS) == []
    assert not os.path.exists(wa._pending_path(wa.SKILLS, r["id"]))


def test_asking_never_rewrites_the_staged_record(hermes_home):
    from tools import write_approval as wa
    r = _stage(wa)
    path = wa._pending_path(wa.SKILLS, r["id"])
    before = open(path, "rb").read()
    assert _call({"action": "ask_approval", "id": r["id"], "note": "worth keeping"})["success"]
    assert open(path, "rb").read() == before
    assert wa.get_approval_request(wa.SKILLS, wa.get_pending(wa.SKILLS, r["id"]))["note"] == "worth keeping"
    assert _call({"action": "list"})["pending"][0]["asked_for_approval"] == "worth keeping"


def test_discard_removes_the_request_too_and_a_stale_one_is_ignored(hermes_home):
    from tools import write_approval as wa
    r = _stage(wa)
    assert _call({"action": "ask_approval", "id": r["id"], "note": "keep this"})["success"]
    ask_file = wa._ask_path(wa.SKILLS, r["id"])
    assert os.path.exists(ask_file)
    assert wa.discard_pending(wa.SKILLS, r["id"]) is True
    assert not os.path.exists(ask_file)
    # an orphan from an earlier record with the same ID must not attach to a new record
    wa.atomic_json_write(ask_file, {"at": 1, "note": "stale", "record_created_at": 123.0})
    fresh = wa.stage_write(wa.SKILLS, {"action": "batch", "operations": []}, summary="s", origin="foreground")
    if fresh["id"] == r["id"]:
        assert wa.get_approval_request(wa.SKILLS, wa.get_pending(wa.SKILLS, fresh["id"])) is None
    assert [x["id"] for x in wa.list_pending(wa.SKILLS)] == [fresh["id"]]       # an .ask file is never a record
