"""Regression checks for the Reed source-only protected input repairs."""
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


@pytest.mark.skipif(os.name != "nt", reason="Windows-specific UNC and namespace behavior")
def test_unc_aliases_ask_and_unrelated_path_does_not():
    from tools import file_tools_write_guards as wg
    with patch.object(wg, "_request_protected_instruction_approval", return_value="ASK"):
        for target in ("//localhost/C$/config.yaml", "//127.0.0.1/C$/temp/file.txt", chr(92)*2 + "localhost" + chr(92) + "C$" + chr(92) + "Windows" + chr(92) + "test.txt"):
            assert wg._check_sensitive_path(target) == "ASK"
        assert wg._check_sensitive_path("C:/an-unrelated-document-root/notes.txt") is None


def test_braces_preserved_in_block_message():
    from tools import file_tools_write_guards as wg
    result = wg._request_protected_instruction_approval(["C:/temp/{0}/config.yaml"])
    assert result is not None and "BLOCKED:" in result and "{0}" in result


def test_literal_why_in_protected_path_remains_literal():
    from tools import file_tools_write_guards as wg
    result = wg._request_protected_instruction_approval(["C:/temp/{why}/config.yaml"])
    assert result is not None and "C:/temp/{why}/config.yaml" in result


def test_hardlink_file_requires_approval(tmp_path):
    import os
    import tempfile
    from pathlib import Path
    from unittest import SkipTest
    from tools import file_tools_write_guards as wg
    if os.name != "nt":
        raise SkipTest("Windows-specific hard-link integration test")
    candidates = [Path(tempfile.gettempdir())]
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidates.append(Path(local_appdata) / "Temp")
    candidates.append(Path(wg.__file__).resolve().parents[3] / "Temp")
    scratch = None
    errors = []
    for candidate in dict.fromkeys(candidates):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            trial = tempfile.TemporaryDirectory(prefix="reed-hl-", dir=str(candidate))
            target = Path(trial.name) / "probe-a.txt"
            target.write_text("x", encoding="utf8")
            os.link(target, Path(trial.name) / "probe-b.txt")
            scratch = trial
            break
        except OSError as exc:
            errors.append(f"{candidate}: {type(exc).__name__}")
            if "trial" in locals():
                trial.cleanup()
    if scratch is None:
        raise SkipTest("No writable Windows hard-link-capable scratch volume: " + "; ".join(errors))
    with scratch as location:
        base = Path(location)
        protected = base / "config.yaml"
        alias = base / "ordinary-notes.txt"
        protected.write_text("approvals: smart", encoding="utf8")
        os.link(protected, alias)
        assert os.path.samefile(protected, alias)
        with patch.object(wg, "_request_protected_instruction_approval", return_value="ASK"):
            assert wg._check_sensitive_path(str(alias)) == "ASK"
            untouched = base / "ordinary-single-link.txt"
            untouched.write_text("safe", encoding="utf8")
            assert wg._check_sensitive_path(str(untouched)) is None


def test_ssh_gate_denies_and_preserves_literal_braces():
    from tools import file_tools_write_guards as wg
    with patch('agent.file_safety.is_write_approval_required', return_value=True):
        with patch('tools.approval._run_approval_gate', return_value={'approved': False}):
            for path in ('C:/Users/test/.ssh/config', 'C:/temp/{why}/config'):
                result = wg._check_approval_required_write([path])
                assert result is not None and 'BLOCKED:' in result and path in result


def test_ssh_gate_allows_only_after_approval():
    from tools import file_tools_write_guards as wg
    with patch('agent.file_safety.is_write_approval_required', return_value=True):
        with patch('tools.approval._run_approval_gate', return_value={'approved': True}) as approve:
            assert wg._check_approval_required_write(['C:/Users/test/.ssh/config']) is None
            assert approve.call_count == 1


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


@pytest.mark.skipif(os.name != "nt", reason="Windows-specific UNC and namespace behavior")
def test_extended_and_nonloopback_unc_paths_ask():
    from tools import file_tools_write_guards as wg
    with patch.object(wg, "_request_protected_instruction_approval", return_value="ASK"):
        host = chr(92)*2
        extended = host+"?"+chr(92)+"UNC"+chr(92)+"localhost"+chr(92)+"C$"+chr(92)+"config.yaml"
        remote = host+"another-server"+chr(92)+"share"+chr(92)+"jobs.json"
        assert "Write denied" in wg._check_sensitive_path(extended)
        with patch.object(wg, "_resolved_or_raw", side_effect=AssertionError("resolver must not run before consent")):
            assert wg._check_sensitive_path(remote) == "ASK"


def test_relative_file_path_uses_task_resolution_not_process_cwd():
    """A relative filename must not falsely resolve into the harness source tree."""
    from tools import file_tools_write_guards as wg
    with patch.object(wg, '_resolved_or_raw', return_value='F:/GPT-Home/scratch/ordinary-file.txt'):
        with patch.object(wg, '_get_hermes_config_resolved', return_value=None):
            with patch.object(wg, '_request_protected_instruction_approval', return_value='ASK') as ask:
                assert wg._check_sensitive_path('ordinary-file.txt') is None
                ask.assert_not_called()


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
