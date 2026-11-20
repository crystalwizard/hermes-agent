"""Owner approval of protected file writes includes change evidence."""
import hashlib
from unittest.mock import patch
from tools import file_tools, file_tools_write_guards as wg


def test_change_preview_hash_and_braces():
    text = "new {value}\n"
    summary = wg._describe_proposed_change(text)
    assert hashlib.sha256(text.encode("utf8")).hexdigest() in summary
    assert "Proposed change" in summary
    assert "UTF-8 bytes" in summary
    assert "new " in summary
    assert "\\u007b" in summary


def test_redacted_change_does_not_expose_raw_secret():
    with patch("agent.redact.redact_sensitive_text", return_value="[REDACTED]"):
        summary = wg._describe_proposed_change("SECRET123")
    assert "SECRET123" not in summary
    assert "redacted" in summary


def test_gateway_owner_card_includes_proposed_change():
    from tools import approval as a
    seen = {}
    def decide(key, cb, payload, **kwargs):
        seen.update(payload)
        return {"choice": "deny", "resolved": True}
    with patch("tools.approval_context.get_current_session_key", return_value="sample"):
        with patch.object(a, "_gateway_notify_cbs", {"sample": lambda x: None}):
            with patch("tools.approval_gateway_wait._await_gateway_decision", side_effect=decide):
                result = wg._request_protected_instruction_approval(
                    ["C:/tmp/SOUL.md"], change_text="changed content")
    assert "BLOCKED" in result
    assert "changed content" in seen["description"]
    assert hashlib.sha256(b"changed content").hexdigest() in seen["description"]
    assert not seen["allow_permanent"] and not seen["allow_session"]


def test_write_file_forwards_full_proposed_content_to_guard():
    seen = {}
    def reject(path, task_id, **kwargs):
        seen.update(kwargs)
        return "BLOCKED: unit test"
    with patch.object(file_tools, "_check_sensitive_path", side_effect=reject):
        result = file_tools.write_file_tool("C:/tmp/SOUL.md", "new text here")
    assert "BLOCKED" in result
    assert seen["change_text"] == "new text here"


def test_patch_forwards_change_summary_to_precheck():
    seen = {}
    def reject(paths, content_paths, task_id, cross_profile, **kwargs):
        seen.update(kwargs)
        return "BLOCKED: unit test"
    with patch.object(file_tools, "_write_precheck_error", side_effect=reject):
        result = file_tools.patch_tool(mode="replace", path="C:/tmp/SOUL.md",
                                       old_string="before", new_string="after")
    assert "BLOCKED" in result
    assert "before" in seen["change_text"] and "after" in seen["change_text"]
