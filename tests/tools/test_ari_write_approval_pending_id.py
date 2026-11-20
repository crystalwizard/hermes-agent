"""Pending-ID validation in tools/write_approval.py (Ari port Step 1, from Reed's S9 hunks).

A pending ID is only ever 8 lowercase hex characters made by stage_write. Anything else must be refused
before it can become part of a path, and must never touch a file outside the pending directory.
"""

import os
import shutil
import tempfile

import pytest


@pytest.fixture
def hermes_home(monkeypatch):
    d = tempfile.mkdtemp(prefix="hermes_wa_pid_")
    home = os.path.join(d, ".hermes")
    os.makedirs(home)
    monkeypatch.setenv("HERMES_HOME", home)
    yield home
    shutil.rmtree(d, ignore_errors=True)


BAD_IDS = [
    "../../escape",
    "..\\..\\escape",
    "ABCDEF12",      # uppercase hex is not what stage_write makes
    "abc",           # too short
    "abcdef123",     # too long
    "abcdefg1",      # not hex
    "abcdef12.json",
    "abcdef12\x00",
    " abcdef1",
]


@pytest.mark.parametrize("bad", BAD_IDS)
def test_bad_id_reads_as_not_found_and_path_is_refused(hermes_home, bad):
    from tools import write_approval as wa
    with pytest.raises(ValueError):
        wa._pending_path(wa.MEMORY, bad)
    assert wa.get_pending(wa.MEMORY, bad) is None


def test_unknown_subsystem_is_refused(hermes_home):
    from tools import write_approval as wa
    with pytest.raises(ValueError):
        wa._pending_path("../skills", "abcdef12")
    assert wa.get_pending("../skills", "abcdef12") is None


def test_discard_with_bad_id_deletes_nothing_outside_pending(hermes_home):
    from tools import write_approval as wa
    victim = os.path.join(hermes_home, "pending", "victim.json")
    os.makedirs(os.path.dirname(victim), exist_ok=True)
    with open(victim, "w", encoding="utf-8") as f:
        f.write("{}")
    assert wa.discard_pending(wa.MEMORY, "../victim") is False
    assert os.path.exists(victim)


def test_valid_staged_record_round_trips_and_directory_lookups_still_work(hermes_home):
    from tools import write_approval as wa
    rec = wa.stage_write(wa.MEMORY, {"a": 1}, summary="s", origin="test")
    pid = rec["id"]
    assert len(pid) == 8 and pid == pid.lower()
    assert wa.get_pending(wa.MEMORY, pid)["id"] == pid
    assert wa.pending_count(wa.MEMORY) == 1
    assert [r["id"] for r in wa.list_pending(wa.MEMORY)] == [pid]
    assert wa.discard_pending(wa.MEMORY, pid) is True
    assert wa.pending_count(wa.MEMORY) == 0


def test_empty_id_is_not_a_record_for_read_or_delete(hermes_home):
    """The empty ID is only for locating the pending directory (Morrow, Step 1 review)."""
    from tools import write_approval as wa
    dot = os.path.join(hermes_home, "pending", wa.MEMORY, ".json")
    os.makedirs(os.path.dirname(dot), exist_ok=True)
    with open(dot, "w", encoding="utf-8") as f:
        f.write('{"id": "dot-file"}')
    assert wa.get_pending(wa.MEMORY, "") is None
    assert wa.discard_pending(wa.MEMORY, "") is False
    assert os.path.exists(dot)
