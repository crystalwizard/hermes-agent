"""Reed security updater: local source changes must not be stashed unbacked."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest

from hermes_cli import update_cmd


def test_dirty_checkout_without_backup_refuses(tmp_path):
    (tmp_path / ".git").mkdir()
    with patch.object(update_cmd.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=" M tools/file_tools_write_guards.py\n")):
        with pytest.raises(RuntimeError, match="local modifications"):
            update_cmd._refuse_update_with_dirty_checkout(tmp_path)


def test_clean_checkout_without_backup_allowed(tmp_path):
    (tmp_path / ".git").mkdir()
    with patch.object(update_cmd.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="")):
        assert update_cmd._refuse_update_with_dirty_checkout(tmp_path) is None


def test_user_snapshot_does_not_protect_dirty_source(tmp_path):
    (tmp_path / ".git").mkdir()
    with patch.object(update_cmd.subprocess, "run", return_value=SimpleNamespace(
            returncode=0, stdout=" M tools/process_registry.py\n")):
        with pytest.raises(RuntimeError, match="pre-update backups exclude"):
            update_cmd._refuse_update_with_dirty_checkout(tmp_path)


def test_git_probe_failure_without_snapshot_refuses(tmp_path):
    (tmp_path / ".git").mkdir()
    with patch.object(update_cmd.subprocess, "run", return_value=SimpleNamespace(returncode=128, stdout="")):
        with pytest.raises(RuntimeError, match="Cannot inspect"):
            update_cmd._refuse_update_with_dirty_checkout(tmp_path)
