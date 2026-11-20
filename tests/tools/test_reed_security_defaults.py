"""Reed source-default and permission-path regression tests."""
import os
from pathlib import Path
from unittest.mock import patch

import pytest


def test_mcp_missing_trust_is_untrusted():
    from tools import mcp_tool as core, mcp_tool_registration as reg
    assert reg._normalize_server_trust(None) == core._TRUST_UNTRUSTED
    assert reg._normalize_server_trust("full") == core._TRUST_FULL


def test_media_missing_strict_fails_closed_but_explicit_false_is_respected():
    from gateway import media_policy as media
    from hermes_cli.config_defaults import DEFAULT_CONFIG
    assert DEFAULT_CONFIG["gateway"]["strict"] is True
    with patch.object(media, "_routed_gateway_cfg", return_value={}):
        assert media.media_delivery_strict() is True
    with patch.object(media, "_routed_gateway_cfg", return_value={"strict": False}):
        assert media.media_delivery_strict() is False
    with patch.object(media, "_routed_gateway_cfg", return_value=None):
        with patch.dict(os.environ, {}, clear=True):
            assert media.media_delivery_strict() is True


def test_webhook_blank_host_is_loopback_and_public_requires_explicit_optin():
    from gateway.platforms.webhook import WebhookAdapter
    from gateway.platforms.base import PlatformConfig
    for extra in ({}, {"host": ""}, {"host": None}):
        assert WebhookAdapter(PlatformConfig(enabled=True, extra=extra))._host == "127.0.0.1"
    assert WebhookAdapter(PlatformConfig(enabled=True, extra={"host": "*"}))._host is None


def test_invalid_existing_config_without_backup_never_uses_defaults():
    from hermes_cli import config as cfg
    path = Path("C:/nonexistent/invalid-config.yaml")
    with patch.object(cfg, "_LAST_EXPANDED_CONFIG_BY_PATH", {}):
        with patch("hermes_cli.config_backups.load_newest_good_backup", return_value=None):
            with patch.object(cfg, "_warn_config_parse_failure"):
                with pytest.raises(cfg.InvalidUserConfigError, match="no usable last-known-good"):
                    cfg._last_known_good_fallback(path, str(path), None, ValueError("invalid YAML"))


def test_invalid_existing_config_keeps_last_good():
    from hermes_cli import config as cfg
    path = Path("C:/nonexistent/invalid-config.yaml")
    good = {"approvals": {"mode": "manual"}}
    with patch.object(cfg, "_LAST_EXPANDED_CONFIG_BY_PATH", {str(path): good}):
        with patch.object(cfg, "_warn_config_parse_failure"):
            result = cfg._last_known_good_fallback(path, str(path), None, ValueError("invalid YAML"))
    assert result["approvals"]["mode"] == "manual"


@pytest.mark.skipif(os.name != "nt", reason="Windows-specific path aliases")
def test_remaining_reed_behavior_and_execution_paths_require_approval():
    from tools import file_tools_write_guards as g
    home = Path("C:/Users/test/AppData/Local/hermes")
    with patch("hermes_constants.get_hermes_home", return_value=home):
        with patch.object(g, "_request_protected_instruction_approval", return_value="ASK"):
            with patch.object(g, "_get_hermes_config_resolved", return_value=None):
                for relative in (
                    "plugins/sample.py", "cron/jobs.json", "bin/a.cmd",
                    "scripts/a.py", "memories/MEMORY.md", "skills/a/SKILL.md",
                    "auth.json", "shell-hooks-allowlist.json",
                    "webhook_subscriptions.json", "SOUL.md",
                ):
                    assert g._check_sensitive_path(str(home / relative)) == "ASK", relative
                for relative in (
                    ".bash_login", ".bash_logout", ".zshrc",
                    ".config/git/config", "project/.git/config",
                    "project/.gitattributes", "project/.gitmodules",
                ):
                    assert g._check_sensitive_path("C:/Users/test/" + relative) == "ASK", relative
                for target in (
                    str(home / "shell-hooks-allowlist.json::$DATA"),
                    "C:/Users/test/.bash_logout::$DATA",
                    "C:/Users/test/AppData/Roaming/npm/unsafe.cmd",
                ):
                    assert g._check_sensitive_path(target) == "ASK", target
                assert g._check_sensitive_path("C:/Users/test/Documents/notes.txt") is None


def test_existing_blank_config_takes_failed_load_path(tmp_path):
    from hermes_cli import config as cfg
    import pytest
    path = tmp_path / "config.yaml"
    path.write_text("# interrupted edit" + chr(10), encoding="utf8")
    with patch.object(cfg, "get_config_path", return_value=path):
        with patch.object(cfg, "ensure_hermes_home"):
            with patch.object(cfg, "_load_config_cache_hit", return_value=None):
                with patch.object(cfg, "_last_known_good_fallback", side_effect=RuntimeError("LKG_USED")) as lkg:
                    with pytest.raises(RuntimeError, match="LKG_USED"):
                        cfg._load_config_impl(want_deepcopy=True)
                    lkg.assert_called_once()


def test_existing_nonmapping_config_takes_failed_load_path(tmp_path):
    from hermes_cli import config as cfg
    import pytest
    path = tmp_path / "config.yaml"
    path.write_text("- this is not a settings mapping" + chr(10), encoding="utf8")
    with patch.object(cfg, "get_config_path", return_value=path):
        with patch.object(cfg, "ensure_hermes_home"):
            with patch.object(cfg, "_load_config_cache_hit", return_value=None):
                with patch.object(cfg, "_last_known_good_fallback", side_effect=RuntimeError("LKG_USED")) as lkg:
                    with pytest.raises(RuntimeError, match="LKG_USED"):
                        cfg._load_config_impl(want_deepcopy=True)
                    lkg.assert_called_once()


@pytest.mark.skipif(os.name != "nt", reason="Windows-specific classifier")
def test_windows_sensitive_executable_and_hermes_paths():
    from tools import file_tools_write_guards as g
    home = Path("C:/Users/example/AppData/Local/hermes")
    with patch("hermes_constants.get_hermes_home", return_value=home):
        sensitive = (
            "C:/Users/example/AppData/Local/Microsoft/WindowsApps/runner.exe",
            "C:/Users/example/.cargo/bin/tool.exe",
            "C:/Users/example/.local/bin/helper.exe",
            "C:/Users/example/AppData/Local/Programs/Python/Python311/Scripts/command.exe",
            "C:/Users/example/AppData/Local/hermes/gateway-service/Hermes_Gateway.cmd",
            "C:/Users/example/AppData/Local/hermes/profiles/bob/config.yaml",
            "C:/Users/example/AppData/Local/hermes/desktop-plugins/launcher.ps1",
            "C:/Users/example/AppData/Local/hermes/runtimes/python.exe",
            "C:/Users/example/AppData/Local/hermes/bot_relay/config.yaml",
        )
        for name in sensitive:
            assert g._windows_sensitive_write_reason(name), name
        assert g._windows_sensitive_write_reason("C:/Users/example/Documents/ordinary.txt") is None


@pytest.mark.skipif(os.name != "nt", reason="Windows-specific classifier")
def test_failed_hermes_home_resolution_never_silently_allows_write():
    from tools import file_tools_write_guards as g
    with patch("hermes_constants.get_hermes_home", side_effect=OSError("no home")):
        with patch.object(g,"_request_protected_instruction_approval",return_value="ASK") as prompt:
            assert g._check_sensitive_path("C:/Users/example/Documents/ordinary.txt") == "ASK"
            prompt.assert_called_once()
    with patch("hermes_constants.get_hermes_home", return_value=Path("C:/Users/example/AppData/Local/hermes")):
        assert g._windows_sensitive_write_reason("C:/Users/example/Documents/ordinary.txt") is None
        assert g._windows_sensitive_write_reason("C:/Users/example/AppData/Local/hermes/cron/jobs.json")


@pytest.mark.skipif(os.name != "nt", reason="Windows-specific Hermes-home policy")
def test_new_hermes_home_paths_are_protected_by_default():
    from tools import file_tools_write_guards as g
    home = Path("C:/Users/example/AppData/Local/hermes")
    with patch("hermes_constants.get_hermes_home", return_value=home):
        for rel in ("new-component/autorun.py", "hermes-setup.exe",
                    "channel_directory.json", "profiles/alice/anything.txt",
                    "logs/repair.sh", "cache/runner.cmd",
                    "cache/innocent.json", "logs/hidden.pth",
                    "image_cache/runner.com", "logs/.hidden.log"):
            assert g._windows_sensitive_write_reason(str(home / rel)), rel
        for rel in ("logs/2026-10-29.log",
                    "audio_cache/voice.wav", "image_cache/photo.jpg"):
            assert g._windows_sensitive_write_reason(str(home / rel)) is None, rel
