"""stage_write must never overwrite an existing pending approval (Morrow finding B and follow-up, 2026-11-13)."""

import os
import shutil
import tempfile
import threading

import pytest


@pytest.fixture
def hermes_home(monkeypatch):
    d = tempfile.mkdtemp(prefix="hermes_wa_uid_")
    home = os.path.join(d, ".hermes")
    os.makedirs(home)
    monkeypatch.setenv("HERMES_HOME", home)
    yield home
    shutil.rmtree(d, ignore_errors=True)


class _FakeUUID:
    def __init__(self, hex_value):
        self.hex = hex_value


def test_colliding_id_is_redrawn_not_overwritten(hermes_home, monkeypatch):
    from tools import write_approval as wa
    draws = iter(["cafefeed" + "0" * 24, "cafefeed" + "1" * 24, "0badf00d" + "2" * 24])
    monkeypatch.setattr(wa.uuid, "uuid4", lambda: _FakeUUID(next(draws)))
    first = wa.stage_write(wa.MEMORY, {"action": "add", "content": "A"}, summary="a", origin="foreground")
    second = wa.stage_write(wa.MEMORY, {"action": "add", "content": "B"}, summary="b", origin="foreground")
    assert first["id"] == "cafefeed"
    assert second["id"] == "0badf00d"
    assert len(wa.list_pending(wa.MEMORY)) == 2
    assert wa.get_pending(wa.MEMORY, "cafefeed")["payload"]["content"] == "A"
    assert wa.get_pending(wa.MEMORY, "0badf00d")["payload"]["content"] == "B"


def test_normal_staging_unchanged(hermes_home):
    from tools import write_approval as wa
    rec = wa.stage_write(wa.MEMORY, {"action": "add", "content": "X"}, summary="x", origin="foreground")
    assert len(rec["id"]) == 8
    assert wa.get_pending(wa.MEMORY, rec["id"])["payload"]["content"] == "X"


def test_retry_exhaustion_never_overwrites_the_first_record(hermes_home, monkeypatch):
    from tools import write_approval as wa
    monkeypatch.setattr(wa.uuid, "uuid4", lambda: _FakeUUID("cafefeed" + "0" * 24))
    first = wa.stage_write(wa.MEMORY, {"action": "add", "content": "A"}, summary="a", origin="foreground")
    second = wa.stage_write(wa.MEMORY, {"action": "add", "content": "B"}, summary="b", origin="foreground")
    assert first["id"] == "cafefeed"
    assert second["id"] == "unstaged"            # nothing staged, and not an ID that points at record A
    assert wa.get_pending(wa.MEMORY, "unstaged") is None
    assert len(wa.list_pending(wa.MEMORY)) == 1
    assert wa.get_pending(wa.MEMORY, "cafefeed")["payload"]["content"] == "A"


def test_simultaneous_writers_never_share_an_id(hermes_home, monkeypatch):
    from tools import write_approval as wa
    n = 8
    lock = threading.Lock()
    state = {"i": 0}

    def fake_uuid():
        with lock:
            i = state["i"]
            state["i"] += 1
        # the first n draws all collide on the same ID; later draws are unique
        return _FakeUUID("cafefeed" + "0" * 24 if i < n else format(i, "08x") + "0" * 24)

    monkeypatch.setattr(wa.uuid, "uuid4", fake_uuid)
    barrier = threading.Barrier(n)
    results = []

    def worker(k):
        barrier.wait()
        results.append(wa.stage_write(wa.MEMORY, {"action": "add", "content": f"W{k}"}, summary="w", origin="foreground"))

    threads = [threading.Thread(target=worker, args=(k,)) for k in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    ids = [r["id"] for r in results]
    assert len(set(ids)) == n and "unstaged" not in ids
    assert len(wa.list_pending(wa.MEMORY)) == n
    for r in results:
        assert wa.get_pending(wa.MEMORY, r["id"])["payload"]["content"] == r["payload"]["content"]
