"""Process-input gate regression tests, ported from Reed's test_reed_protected_input_regressions.py (process tests only)."""
import os
import pytest
from unittest.mock import patch


def test_process_control_keys_and_visible_normal_input():
    from tools import process_registry as pr
    from tools import file_tools_write_guards as wg
    session = type("TestSession", (), {"command": "cmd"})()
    with patch.object(pr.process_registry, "get", return_value=session), (
        patch.object(wg, "_request_protected_instruction_approval", return_value="ASK")
    ):
        for value in ("\t", "\x1b[A", "\x08"):
            assert pr._gate_process_input("test", "submit", value).startswith("BLOCKED")
        for value in ("hello", "    indented text\n", "\n", "\x03"):
            assert pr._gate_process_input("test", "submit", value) == "ASK"


def test_redaction_is_forced_and_mismatched_input_refused():
    from tools import process_registry as pr
    from tools import file_tools_write_guards as wg
    session = type("TestSession", (), {"command": "cmd"})()
    with patch.object(pr.process_registry, "get", return_value=session), (
        patch.object(wg, "_request_protected_instruction_approval", return_value="ASK")
    ), patch("agent.redact.redact_sensitive_text", side_effect=lambda text, force=False: (
        "[masked]" if force else text
    )) as redact:
        assert pr._gate_process_input("test", "submit", "private input").startswith("BLOCKED")
        assert redact.call_args.kwargs["force"] is True


def test_process_card_escapes_nonprinting_unicode_and_braces():
    from tools import process_registry as pr
    from tools import file_tools_write_guards as wg
    session = type("TestSession", (), {"command": "python"})()
    with patch.object(pr.process_registry, "get", return_value=session):
        with patch.object(wg, "_request_protected_instruction_approval", return_value="ASK") as ask:
            assert pr._gate_process_input("test", "submit", "print({1})" + "\u202e" + "\u200b") == "ASK"
    shown = ask.call_args.args[0][0]
    assert chr(92)+"u007b" in shown and chr(92)+"u007d" in shown
    assert chr(92)+"u202e" in shown and chr(92)+"u200b" in shown
    assert "\u202e" not in shown.replace(chr(92)+"u202e", "") 


def test_process_input_limit_denies_unreviewed_tail():
    from tools import process_registry as pr
    from tools import file_tools_write_guards as wg
    session = type("TestSession", (), {"command": "python"})()
    with patch.object(pr.process_registry, "get", return_value=session):
        with patch.object(wg, "_request_protected_instruction_approval", return_value="ASK") as ask:
            assert pr._gate_process_input("test", "submit", "x"*2001).startswith("BLOCKED")
            ask.assert_not_called()
            assert pr._gate_process_input("test", "submit", "x"*2000) == "ASK"
            assert len(ask.call_args.args[0][0]) >= 2000


def test_process_input_rejects_oversized_escaped_card_but_allows_plain_limit():
    from tools import process_registry as pr
    from tools import file_tools_write_guards as wg
    session = type("TestSession", (), {"command": "python"})()
    with patch.object(pr.process_registry, "get", return_value=session):
        with patch.object(wg, "_request_protected_instruction_approval", return_value="ASK") as ask:
            escaped = chr(0x202e) * 350
            assert "BLOCKED" in pr._gate_process_input("test", "submit", escaped)
            ask.assert_not_called()
            assert pr._gate_process_input("test", "submit", "a" * 2000) == "ASK"
            assert len(ask.call_args.args[0][0]) >= 2000


def test_process_card_long_command_discloses_truncation_and_full_fingerprint():
    import hashlib
    from tools import process_registry as pr
    from tools import file_tools_write_guards as wg
    long_command = "python " + "x" * 220 + " --dangerous-hidden-tail"
    session = type("TestSession", (), {"command": long_command})()
    with patch.object(pr.process_registry, "get", return_value=session):
        with patch.object(wg, "_request_protected_instruction_approval", return_value="ASK") as approval:
            assert pr._gate_process_input("test", "submit", "print(1)") == "ASK"
    shown = approval.call_args.args[0][0]
    assert "command shortened" in shown
    assert hashlib.sha256(long_command.encode("utf-8")).hexdigest() in shown
    assert "print(1)" in shown
