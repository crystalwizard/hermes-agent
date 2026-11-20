"""Reed-local regression: persistent memory is fallible bootstrap data, not canonical truth."""

from agent.context_compressor import SUMMARY_PREFIX
from agent.prompt_builder import build_memory_guidance


def test_live_compaction_prefix_does_not_make_memory_absolute():
    assert "ALWAYS authoritative" not in SUMMARY_PREFIX
    assert "frozen session-start snapshot" in SUMMARY_PREFIX
    assert "canonical file" in SUMMARY_PREFIX
    assert "current source wins" in SUMMARY_PREFIX


def test_memory_guidance_gives_current_canonical_sources_precedence():
    guidance = build_memory_guidance(True, True)
    assert "fallible bootstrap/reference data" in guidance
    assert "current canonical source wins" in guidance
    assert "verify before asserting" in guidance


def test_user_profile_guidance_is_also_fallible_snapshot():
    guidance = build_memory_guidance(False, True)
    assert "fallible reference data" in guidance
    assert "current user statements" in guidance
    assert "current canonical user records win conflicts" in guidance
