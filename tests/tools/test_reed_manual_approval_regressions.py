from types import SimpleNamespace
from unittest.mock import patch
from tools import approval as a


def _manual_baseline():
    return (patch.object(a.approval_context, "_get_approval_mode", return_value="manual"),
            patch.object(a, "_yolo_active", return_value=False),
            patch.object(a, "_command_matches_permanent_allowlist", return_value=False),
            patch.object(a, "_floor_block", return_value=None),
            patch("agent.terminal_approval_batch.consume_prepared_guard", return_value=None))


def test_safe_manual_command_requires_attended_approval():
    from contextlib import ExitStack
    with ExitStack() as stack:
        for p in _manual_baseline(): stack.enter_context(p)
        stack.enter_context(patch.object(a, "_presence", return_value=(None, True, False, False)))
        stack.enter_context(patch.object(a, "_tirith_scan", return_value={"action":"allow","findings":[]}))
        stack.enter_context(patch.object(a,"detect_dangerous_command",return_value=(False,"","")))
        human=stack.enter_context(patch.object(a,"_human_decision",return_value={"approved":False,"message":"DENIED"}))
        r=a.check_all_command_guards("echo hello","local")
        assert r["approved"] is False
        human.assert_called_once()
        assert human.call_args.kwargs["pattern_key"].startswith("manual:terminal:")
        assert human.call_args.kwargs["permanent_capable"] is False


def test_different_manual_commands_have_distinct_approval_keys():
    from contextlib import ExitStack
    with ExitStack() as stack:
        for p in _manual_baseline(): stack.enter_context(p)
        stack.enter_context(patch.object(a, "_presence", return_value=(None, True, False, False)))
        stack.enter_context(patch.object(a, "_tirith_scan", return_value={"action":"allow","findings":[]}))
        stack.enter_context(patch.object(a,"detect_dangerous_command",return_value=(False,"","")))
        human=stack.enter_context(patch.object(a,"_human_decision",return_value={"approved":False}))
        for command in ("echo hello","echo goodbye"):
            a.check_all_command_guards(command,"local")
        assert len({c.kwargs["pattern_key"] for c in human.call_args_list})==2


def test_headless_without_context_matches_ari_legacy_approval():
    from contextlib import ExitStack
    with ExitStack() as stack:
        for p in _manual_baseline(): stack.enter_context(p)
        stack.enter_context(patch.object(a,"_presence",return_value=(None,False,False,False)))
        stack.enter_context(patch.object(a,"_unattended_contexts",return_value=[]))
        r=a.check_all_command_guards("echo hello","local")
        assert r["approved"]


def test_explicit_unattended_approve_policy_respected():
    from contextlib import ExitStack
    with ExitStack() as stack:
        for p in _manual_baseline(): stack.enter_context(p)
        stack.enter_context(patch.object(a,"_presence",return_value=(None,False,False,False)))
        stack.enter_context(patch.object(a,"_unattended_contexts",return_value=[SimpleNamespace(name="cron")]))
        stack.enter_context(patch.object(a,"_unattended_deny",return_value=None))
        r=a.check_all_command_guards("echo hello","local")
        assert r["approved"]

"""Reed human whole-script approval must not authorize redacted executable code."""
from unittest.mock import patch

def _call(code):
    from tools import approval
    return approval._human_decision(
        approval._EXECUTE_CODE_GATE,
        command="execute_code start\n"+code+"\nend",
        description="execute_code script execution",
        pattern_key="execute_code",
        pattern_keys=["execute_code"],
        warnings=[("execute_code",None,False)],
        session_key="reed-visible-test",
        approval_callback=lambda *a,**k:"once",
        is_cli=True,is_gateway=False,is_ask=False,
        smart=False,permanent_capable=False,
        pending_body=lambda:"script body",
    )

def test_hidden_script_denied_without_asking():
    from tools import approval
    with patch("agent.redact.redact_sensitive_text", side_effect=lambda s,force=False:"[hidden]" if force else s):
        with patch.object(approval,"prompt_dangerous_approval",return_value="once") as human:
            result=_call("SECRET")
    assert not result["approved"],result
    assert "hidden" in result["message"].lower()
    human.assert_not_called()

def test_ordinary_script_can_receive_approval():
    from tools import approval
    with patch("agent.redact.redact_sensitive_text",side_effect=lambda s,force=False:s):
        with patch.object(approval,"prompt_dangerous_approval",return_value="once") as human:
            result=_call("print(1)")
    assert result["approved"],result
    human.assert_called_once()
