"""An approval card closed without an answer is withdrawn with an honest reason (Kelly's live test, 2026-11-13)."""

from unittest.mock import patch


def test_closed_card_is_withdrawn_with_an_honest_reason():
    from tui_gateway import server, server_requests
    from tools import approval as _approval
    causes = []

    def fake_send_async(method, sid, payload, on_result):
        on_result(None)                      # the client closed the card: an error reply, no answer
        return lambda reason: None

    with patch.object(server_requests, "send_async", fake_send_async), \
         patch.object(_approval, "withdraw_gateway_approval", lambda key, rid, cause: causes.append(cause) or True), \
         patch.object(_approval, "register_gateway_settle", lambda *a, **k: None):
        server._emit_approval_request("sid-test", {"request_id": "r1", "command": "echo hi", "description": "test"})
    assert len(causes) == 1
    assert "update the Hermes app" not in causes[0]
    assert "sent a new message" in causes[0] and "cannot show approval prompts" in causes[0]
