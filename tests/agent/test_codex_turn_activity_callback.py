"""The codex turn thread answers server requests (human approvals) synchronously.

The tool-layer activity callback is thread-local and the native tool executor binds it on its worker threads.
Without a binding on the codex turn thread, the human-approval wait's heartbeat is a no-op, and a card left
unanswered past the liveness window gets the turn force-interrupted. ``run_codex_app_server_turn`` therefore
binds ``agent._touch_activity`` for the duration of the turn and restores the previous callback afterwards.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agent.codex_runtime import _codex_turn_activity_callback, run_codex_app_server_turn
from tools.environments.base import get_activity_callback, set_activity_callback


@pytest.fixture(autouse=True)
def _clean_activity_callback():
    set_activity_callback(None)
    yield
    set_activity_callback(None)


def _turn():
    return SimpleNamespace(
        interrupted=False, error=None, thread_id="thread-1", turn_id="turn-1",
        projected_messages=[{"role": "assistant", "content": "ok"}], tool_iterations=0,
        final_text="ok", should_retire=False,
    )


def _agent():
    agent = MagicMock()
    agent._codex_session = MagicMock()
    agent._codex_session_prompt = None
    agent.tool_progress_callback = None
    agent._iters_since_skill = 0
    agent._skill_nudge_interval = 0
    agent.valid_tool_names = set()
    agent._session_db = None
    agent._session_db_created = True
    agent.session_id = "sess-codex"
    return agent


def _run(agent):
    return run_codex_app_server_turn(
        agent, user_message="hi", original_user_message="hi",
        messages=[{"role": "user", "content": "hi"}], effective_task_id="task-1",
    )


def test_turn_thread_has_the_agents_activity_callback_while_the_session_runs():
    agent = _agent()
    seen = []
    agent._codex_session.run_turn.side_effect = lambda **_kw: seen.append(get_activity_callback()) or _turn()

    _run(agent)

    assert seen == [agent._touch_activity]
    assert get_activity_callback() is None


def test_previous_callback_is_restored_after_the_turn():
    previous = MagicMock(name="previous_callback")
    set_activity_callback(previous)
    agent = _agent()
    agent._codex_session.run_turn.return_value = _turn()

    _run(agent)

    assert get_activity_callback() is previous


def test_callback_is_restored_when_the_turn_raises():
    previous = MagicMock(name="previous_callback")
    set_activity_callback(previous)
    agent = _agent()
    agent._codex_session.run_turn.side_effect = RuntimeError("codex exploded")

    result = _run(agent)

    assert result["completed"] is False
    assert get_activity_callback() is previous


def test_agent_without_touch_activity_is_left_alone():
    agent = SimpleNamespace()  # no _touch_activity
    previous = MagicMock(name="previous_callback")
    set_activity_callback(previous)

    with _codex_turn_activity_callback(agent):
        assert get_activity_callback() is previous

    assert get_activity_callback() is previous
