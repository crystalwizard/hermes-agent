"""Fail-closed shell hooks (Ari port Step 3, Reed's rule): a fail-closed blocking hook that fails in ANY way blocks.

Exit 0 with empty output is still allowed. Hooks that are not fail-closed, and non-blocking events, still allow.
"""
import json

import pytest

from agent import shell_hooks as sh

SCRIPT = "hook-script-never-executed.py"


def _spec(event="pre_tool_call", fail_closed=True):
    return sh.ShellHookSpec(event=event, command=SCRIPT, matcher="^terminal$", timeout=5, fail_closed=fail_closed)


def _result(rc=0, out="", err="", error=None, timed_out=False):
    return dict(error=error, timed_out=timed_out, elapsed_seconds=0.1, returncode=rc, stdout=out, stderr=err)


def _kind(value):
    if value is None:
        return "allow"
    return "block" if value.get("action") == "block" else "other"


@pytest.mark.parametrize("rc,out,err", [
    (1, "", "boom"),                      # crash with no output
    (1, "{}", ""),                        # crash, but stdout looks like an allow-ish JSON object
    (1, json.dumps({"action": "allow"}), ""),
    (3, "ok", ""),                        # any other non-zero code
    (127, "", "not found"),
])
def test_fail_closed_blocks_on_any_non_zero_exit(rc, out, err):
    assert _kind(sh._evaluate_result(_spec(), _result(rc, out, err))) == "block"


def test_fail_closed_exit_two_still_blocks_with_stderr_message():
    v = sh._evaluate_result(_spec(), _result(2, "", "denied by hook"))
    assert _kind(v) == "block" and "denied by hook" in v["message"]


def test_fail_closed_blocks_on_timeout_and_spawn_error_and_garbage_stdout():
    assert _kind(sh._evaluate_result(_spec(), _result(0, timed_out=True))) == "block"
    assert _kind(sh._evaluate_result(_spec(), _result(0, error="cannot spawn"))) == "block"
    assert _kind(sh._evaluate_result(_spec(), _result(0, "Traceback (most recent call last)"))) == "block"


def test_exit_zero_empty_output_still_allows():
    assert _kind(sh._evaluate_result(_spec(), _result(0, ""))) == "allow"


def test_explicit_block_json_with_exit_zero_blocks():
    assert _kind(sh._evaluate_result(_spec(), _result(0, json.dumps({"action": "block", "message": "no"})))) == "block"


def test_not_fail_closed_still_allows_on_crash():
    assert _kind(sh._evaluate_result(_spec(fail_closed=False), _result(1, "", "boom"))) == "allow"
    assert _kind(sh._evaluate_result(_spec(fail_closed=False), _result(0, ""))) == "allow"


def test_fail_closed_ignored_on_non_blocking_event():
    assert _kind(sh._evaluate_result(_spec(event="pre_llm_call"), _result(1, "", "boom"))) == "allow"
