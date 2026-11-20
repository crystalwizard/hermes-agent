"""An allowlisted shell hook is only trusted at registration if its script is unchanged since approval.

Approval records the script's mtime; _allowlist_still_valid must refuse when the script has been modified since.
"""
from agent import shell_hooks as sh

CMD = "some-hook-script.py"


def _entry(recorded):
    return {"event": "pre_tool_call", "command": CMD, "script_mtime_at_approval": recorded}


def test_not_allowlisted_is_invalid(monkeypatch):
    monkeypatch.setattr(sh, "allowlist_entry_for", lambda event, command: None)
    assert sh._allowlist_still_valid("pre_tool_call", CMD) is False


def test_unchanged_script_is_valid(monkeypatch):
    monkeypatch.setattr(sh, "allowlist_entry_for", lambda event, command: _entry("2026-11-09T10:00:00Z"))
    monkeypatch.setattr(sh, "script_mtime_iso", lambda command: "2026-11-09T10:00:00Z")
    assert sh._allowlist_still_valid("pre_tool_call", CMD) is True


def test_modified_script_is_no_longer_trusted(monkeypatch):
    monkeypatch.setattr(sh, "allowlist_entry_for", lambda event, command: _entry("2026-11-09T10:00:00Z"))
    monkeypatch.setattr(sh, "script_mtime_iso", lambda command: "2026-11-09T12:34:56Z")
    assert sh._allowlist_still_valid("pre_tool_call", CMD) is False


def test_entry_without_recorded_mtime_is_trusted_as_before(monkeypatch):
    monkeypatch.setattr(sh, "allowlist_entry_for", lambda event, command: _entry(None))
    monkeypatch.setattr(sh, "script_mtime_iso", lambda command: "2026-11-09T12:34:56Z")
    assert sh._allowlist_still_valid("pre_tool_call", CMD) is True
