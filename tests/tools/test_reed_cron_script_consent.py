"""Scheduled script jobs must require fresh owner consent at registration."""
from unittest.mock import patch
from tools import cronjob_tools as c


def test_cron_script_consent_denial():
    with patch("tools.file_tools_write_guards._request_protected_instruction_approval",
               return_value="BLOCKED: no human") as ask:
        result = c._require_cron_script_approval(["scripts/job.py"])
    assert "BLOCKED:" in result
    ask.assert_called_once()


def test_cron_no_script_keeps_prompt_only_jobs_unaffected():
    with patch("tools.file_tools_write_guards._request_protected_instruction_approval") as ask:
        assert c._require_cron_script_approval([]) is None
        ask.assert_not_called()


def test_cron_create_rejects_script_before_scheduler_registration():
    args = {
        "prompt": None, "script": "scripts/job.py", "deliver": None,
        "schedule": "* * * * *", "skill": None, "skills": [],
        "no_agent": True, "monitor_script": None,
        "provider": None, "base_url": None,
        "failure_deliver": None, "context_from": None,
    }
    with patch.object(c, "_validate_cron_script_path", return_value=None):
        with patch.object(c, "_require_cron_script_approval", return_value="BLOCKED: deny") as ask:
            result = c._action_create(args)
    assert "BLOCKED" in result
    ask.assert_called_once_with(["scripts/job.py"])


def test_cron_script_update_blocks_before_mutation():
    job = {"id": "cron-test", "script": "scripts/old.py"}
    args = {}
    with patch.object(c, "_UPDATE_STEPS", (
        lambda _job, _args, updates: updates.update({"script": "scripts/new.py"}) or None,
    )):
        with patch.object(c, "_require_cron_script_approval", return_value="BLOCKED: denied") as ask:
            with patch.object(c, "update_job") as mutate:
                result = c._action_update(job, args)
    assert "BLOCKED" in result
    mutate.assert_not_called()
    ask.assert_called_once_with(["scripts/new.py"])
