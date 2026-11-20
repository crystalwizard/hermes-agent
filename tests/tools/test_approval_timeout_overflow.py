"""Regression tests for #83220: oversized approvals.timeout must never
overflow platform wait primitives (macOS time_t and Windows DWORD millisecond limits).

The clamp lives at the single config-read site (_get_approval_timeout), so
every consumer — CLI prompt thread.join, gateway poll deadline, human-wait
ceiling, and the tool_executor authorization gate — is covered at once.
"""

from __future__ import annotations

import threading

from unittest.mock import patch

from agent.deadline import MAX_SAFE_TIMEOUT_S

PLATFORM_APPROVAL_CAP = min(int(MAX_SAFE_TIMEOUT_S), max(0, int(threading.TIMEOUT_MAX - 61)))


def _with_configured_timeout(value):
    return patch(
        "tools.approval_context._get_approval_config",
        return_value={"timeout": value},
    )


class TestApprovalTimeoutOverflowClamp:
    def test_normal_value_passes_through(self):
        from tools.approval_context import _get_approval_timeout

        with _with_configured_timeout(300):
            assert _get_approval_timeout() == 300

    def test_oversized_value_clamped(self):
        from tools.approval_context import _get_approval_timeout

        with _with_configured_timeout(10**18):
            assert _get_approval_timeout() == PLATFORM_APPROVAL_CAP

    def test_invalid_value_falls_back_to_default(self):
        from tools.approval_context import _get_approval_timeout

        with _with_configured_timeout("soon"):
            assert _get_approval_timeout() == 300

    def test_infinite_numeric_values_do_not_escape_timeout_reader(self):
        from tools.approval_context import _get_approval_timeout
        for value in (float("inf"), float("-inf")):
            with _with_configured_timeout(value):
                assert _get_approval_timeout() == 300

    def test_negative_value_uses_finite_default(self):
        from tools.approval_context import _get_approval_timeout
        from tools.approval_human_wait import human_wait_ceiling
        with _with_configured_timeout(-1):
            assert _get_approval_timeout() == 300
            assert human_wait_ceiling() == 360.0

    def test_zero_value_preserved(self):
        from tools.approval_context import _get_approval_timeout
        with _with_configured_timeout(0):
            assert _get_approval_timeout() == 0

    def test_oversized_float_value_clamped(self):
        # YAML `1e18` arrives as a float, not an int — different int() path
        # than the string/int forms; the clamp must cover it too.
        from tools.approval_context import _get_approval_timeout

        with _with_configured_timeout(1e18):
            assert _get_approval_timeout() == PLATFORM_APPROVAL_CAP



    def test_mocked_small_platform_wait_limit_reserves_margin(self, monkeypatch):
        from tools.approval_context import _get_approval_timeout
        from tools.approval_human_wait import human_wait_ceiling
        monkeypatch.setattr(threading, "TIMEOUT_MAX", 120.0)
        with _with_configured_timeout(10**18):
            assert _get_approval_timeout() == 59
            assert human_wait_ceiling() == 119.0

    def test_clamped_value_safe_for_lock_acquire(self):
        # The exact primitive that crashed in #83220: Lock.acquire on macOS
        # converts the relative timeout to an absolute time_t timestamp.
        from tools.approval_context import _get_approval_timeout

        with _with_configured_timeout(10**18):
            timeout = _get_approval_timeout()
        lock = threading.Lock()
        assert lock.acquire(timeout=timeout)  # would raise OverflowError unclamped
        lock.release()


    def test_human_wait_ceiling_inherits_clamp(self):
        from tools.approval_human_wait import HUMAN_WAIT_MARGIN_S, human_wait_ceiling

        with _with_configured_timeout(10**18):
            ceiling = human_wait_ceiling()
        assert ceiling == float(PLATFORM_APPROVAL_CAP) + HUMAN_WAIT_MARGIN_S
        lock = threading.Lock()
        assert lock.acquire(timeout=ceiling)
        lock.release()

    def test_authorization_gate_timeout_safe_and_extends_with_config(self):
        # The gate bound must (a) be platform-safe with an oversized config
        # and (b) still EXTEND beyond the 360s fallback when approvals.timeout
        # is legitimately larger — clamping it down to the fallback would
        # break serialization while a real prompt is still answerable (#79719).
        from agent.tool_executor import (
            _AUTHORIZATION_GATE_LOCK_TIMEOUT_S,
            _authorization_gate_lock_timeout,
        )

        with _with_configured_timeout(10**18):
            bound = _authorization_gate_lock_timeout()
        lock = threading.Lock()
        assert lock.acquire(timeout=bound)
        lock.release()

        with _with_configured_timeout(3600):
            bound = _authorization_gate_lock_timeout()
        assert bound > _AUTHORIZATION_GATE_LOCK_TIMEOUT_S
        assert bound == 3600 + 60.0  # approvals.timeout + HUMAN_WAIT_MARGIN_S
