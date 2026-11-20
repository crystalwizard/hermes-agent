"""Reed browser_exec must never bypass host code-approval checks."""
from unittest.mock import patch
from tools import browser_use_cli as b


def test_browser_exec_denial_never_launches_cli():
    with patch("tools.approval.check_execute_code_guard",
               return_value={"approved": False, "message": "BLOCKED: owner denied"}):
        with patch.object(b, "_find_cli") as cli:
            outcome = b.browser_exec("print(1)")
            cli.assert_not_called()
    assert "BLOCKED" in str(outcome)


def test_browser_exec_checks_code_guard_before_cli_lookup():
    with patch("tools.approval.check_execute_code_guard",
               return_value={"approved": True}) as guardian:
        with patch.object(b, "_find_cli", return_value=None):
            outcome = b.browser_exec("print(1)")
    guardian.assert_called_once()
    assert guardian.call_args.kwargs["env_type"] == "local"
    assert guardian.call_args.kwargs["has_host_access"] is True
    assert "not found" in str(outcome).lower()
