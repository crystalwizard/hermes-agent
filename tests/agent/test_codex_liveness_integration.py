"""Shortened-watchdog integration tests: do the liveness seams compose?

The unit tests show each seam is wired. These drive the REAL pieces together with shortened time constants
(no ten-minute waits): the real ``TurnLivenessWatchdog``, the real ``_touch_activity`` activity clock, the real
Desktop/gateway human-approval wait (``request_tool_approval`` -> ``_poll_event`` heartbeat), the real
``_codex_turn_activity_callback`` binding, and the real Codex event bridge.

1. A pending human approval that outlives the watchdog threshold must NOT get the turn aborted when the activity
   callback is bound on the codex turn thread (and DOES without it: the control proves the harness can see it).
2. Periodic Codex notifications keep an active, tool-only turn alive past the threshold, while genuine silence
   still lets the watchdog regain authority and abort.
"""

import contextlib
import threading
import time
from unittest.mock import MagicMock

import pytest

import tools.approval as approval
import tools.approval_context as tools_approval_context
import tools.approval_gateway_wait as approval_gateway_wait
from agent.activity_tracking import ActivityTrackingMixin, _activity_lock
from agent.codex_runtime import _codex_turn_activity_callback, make_codex_app_server_event_bridge
from agent.turn_liveness import TurnLivenessWatchdog
from tools.environments.base import touch_activity_if_due

TIMEOUT_S = 2.5          # shortened watchdog threshold (production default: 600 s)
POLL_S = 0.05
SESSION_KEY = "codex-liveness-integration"


class _Agent(ActivityTrackingMixin):
    """The real activity clock; nothing else of AIAgent is needed here."""


def _start_watchdog(agent, turn_active):
    aborts = []
    watchdog = TurnLivenessWatchdog(
        agent, session_id="s", timeout_s=TIMEOUT_S, poll_s=POLL_S, stop_event=threading.Event(),
        activity_lock=_activity_lock(agent), is_turn_active=turn_active.is_set,
        commit_abort=lambda snapshot, message: aborts.append(time.monotonic()) or True,
        deactivate_turn=lambda: None,
    )

    def loop():
        while watchdog._tick() is None:
            time.sleep(POLL_S)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    return aborts, thread


@pytest.fixture
def agent():
    a = _Agent()
    a._touch_activity("turn start")
    return a


@pytest.fixture
def turn_active():
    event = threading.Event()
    event.set()
    yield event
    event.clear()


@pytest.fixture
def desktop_gateway(monkeypatch):
    """A Desktop-like process: gateway approval path, a fast activity heartbeat, no remembered approvals."""
    monkeypatch.setattr(approval, "get_current_session_key", lambda default="default": SESSION_KEY)
    monkeypatch.setattr(approval, "_is_interactive_cli", lambda: False)
    monkeypatch.setattr(approval, "_is_gateway_approval_context", lambda: True)
    monkeypatch.setattr(tools_approval_context, "_is_gateway_approval_context", lambda: True)
    monkeypatch.setattr(approval, "is_current_session_yolo_enabled", lambda: False)
    monkeypatch.setattr(approval, "is_approved", lambda *_a: False)
    monkeypatch.setattr(tools_approval_context, "_get_approval_timeout", lambda: 60)

    def fast_heartbeat(label):
        state = {"last_touch": time.monotonic(), "start": time.monotonic(), "interval": 0.2}
        return lambda: touch_activity_if_due(state, label)

    monkeypatch.setattr(approval_gateway_wait, "activity_heartbeat", fast_heartbeat)
    yield
    approval.clear_session(SESSION_KEY)


def _answer_after(delay_s):
    """Register the Desktop card listener; it answers 'once' after *delay_s* seconds."""
    def on_card(data):
        threading.Timer(
            delay_s,
            lambda: approval.resolve_gateway_approval(SESSION_KEY, "once", request_id=data["request_id"]),
        ).start()

    approval.register_gateway_notify(SESSION_KEY, on_card)


def _pending_approval(agent, *, bind):
    box = {}

    def run():
        binding = _codex_turn_activity_callback(agent) if bind else contextlib.nullcontext()
        with binding:
            box["result"] = approval.request_tool_approval(
                "codex_permissions", "Codex requests network access", rule_key="liveness-integration",
                allow_global_bypass=False, require_human=True,
            )

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return box, thread


def test_pending_approval_outlives_the_watchdog_when_the_callback_is_bound(agent, turn_active, desktop_gateway):
    hold = TIMEOUT_S * 2
    _answer_after(hold)
    aborts, watchdog_thread = _start_watchdog(agent, turn_active)
    try:
        started = time.monotonic()
        box, thread = _pending_approval(agent, bind=True)
        thread.join(timeout=hold + 10)

        assert not thread.is_alive()
        assert time.monotonic() - started >= TIMEOUT_S, "the approval must have outlived the watchdog threshold"
        assert box["result"]["approved"] is True
        assert aborts == [], "the watchdog must not abort a turn that is waiting on a person"
    finally:
        approval.unregister_gateway_notify(SESSION_KEY)
        turn_active.clear()
        watchdog_thread.join(timeout=2)


def test_control_without_the_binding_the_watchdog_aborts_a_pending_approval(agent, turn_active, desktop_gateway):
    """The harness must be able to see the original failure: with no activity callback on the turn thread the
    approval heartbeat is a no-op, and the watchdog aborts the turn while the card is still unanswered."""
    hold = TIMEOUT_S * 2
    _answer_after(hold)
    aborts, watchdog_thread = _start_watchdog(agent, turn_active)
    try:
        box, thread = _pending_approval(agent, bind=False)
        deadline = time.monotonic() + TIMEOUT_S * 3
        while not aborts and time.monotonic() < deadline:
            time.sleep(0.05)

        assert aborts, "without the binding the idle clock must run out and the watchdog must fire"
        assert thread.is_alive(), "the card was still unanswered when the watchdog fired"
    finally:
        approval.unregister_gateway_notify(SESSION_KEY)
        thread.join(timeout=hold + 10)
        turn_active.clear()
        watchdog_thread.join(timeout=2)


def test_periodic_codex_notifications_keep_a_tool_only_turn_alive_and_silence_does_not(agent, turn_active):
    bridge = make_codex_app_server_event_bridge(agent)
    aborts, watchdog_thread = _start_watchdog(agent, turn_active)
    try:
        busy_for = TIMEOUT_S * 1.6
        started = time.monotonic()
        last_notification = started
        while time.monotonic() - started < busy_for:
            # A turn doing tool work: no display text, just codex notifications on a timer.
            bridge({"method": "thread/tokenUsage/updated", "params": {}})
            last_notification = time.monotonic()
            time.sleep(0.2)
        assert aborts == [], "notifications arriving inside the window must keep the turn alive"

        deadline = last_notification + TIMEOUT_S * 3
        while not aborts and time.monotonic() < deadline:
            time.sleep(0.05)

        assert aborts, "once notifications truly stop, the watchdog must regain authority"
        assert aborts[0] - last_notification >= TIMEOUT_S - 0.5, "it must not fire before the window elapsed"
    finally:
        turn_active.clear()
        watchdog_thread.join(timeout=2)
