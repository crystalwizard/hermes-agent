"""A missing sandbox root must not make interpreter shutdown raise."""
from unittest.mock import patch


def test_cleanup_orphan_scan_permission_error_does_not_abort():
    from tools import terminal_tool_lifecycle as life
    with patch("tools.terminal_tool._active_environments", {}):
        with patch.object(life, "_scratch_paths", side_effect=PermissionError("no sandbox access")):
            assert life.cleanup_all_environments() == 0


def test_cleanup_running_environments_continues_when_orphan_scan_fails():
    from tools import terminal_tool_lifecycle as life
    with patch("tools.terminal_tool._active_environments", {"test": object()}):
        with patch.object(life, "cleanup_vm") as cleanup:
            with patch.object(life, "_scratch_paths", side_effect=PermissionError("no sandbox access")):
                assert life.cleanup_all_environments() == 1
    cleanup.assert_called_once_with("test")
