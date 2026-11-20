from unittest.mock import patch
from tools import approval as a


def test_allowlisted_tirith_session_grant_and_isolation():
    finding = {"action": "warn", "findings": [{"rule_id": "replay-1"}]}
    with patch.object(a.approval_context, "_get_approval_mode", return_value="manual"),          patch.object(a, "_yolo_active", return_value=False),          patch.object(a, "_floor_block", return_value=None),          patch("agent.terminal_approval_batch.consume_prepared_guard", return_value=None),          patch.object(a, "_command_matches_permanent_allowlist", return_value=True),          patch.object(a, "_tirith_scan", return_value=finding),          patch.object(a, "_presence", return_value=(None, True, False, False)),          patch.object(a, "get_current_session_key", return_value="s1"),          patch.object(a, "is_approved", side_effect=[False, True, False]),          patch.object(a, "_human_decision", return_value={"approved": True}) as ask:
        assert a.check_all_command_guards("echo sample", "local")["approved"]
        assert a.check_all_command_guards("echo sample", "local")["approved"]
        assert a.check_all_command_guards("echo sample", "local")["approved"]
        assert ask.call_count == 2


def test_unclassified_scanner_finding_is_command_scoped():
    from tools.approval import _tirith_approval_key
    one = _tirith_approval_key("echo first", {})
    two = _tirith_approval_key("echo second", {})
    assert one.startswith("tirith:unclassified:")
    assert one != two
    assert _tirith_approval_key("echo first", {"rule_id": "unknown"}) == one
    assert _tirith_approval_key("echo first", {"rule_id": "known-rule"}).startswith("tirith:known-rule:")
    assert _tirith_approval_key("echo first", {"rule_id": "known-rule"}) != _tirith_approval_key("echo second", {"rule_id": "known-rule"})
