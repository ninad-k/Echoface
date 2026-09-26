import json

import pytest

from echoface.stages.script import (
    ScriptGenerationError,
    ScriptOutput,
    script_from_plain_text,
    target_word_range,
    validate_script_json,
)


def _valid_payload(n_filler_words=0):
    filler = " ".join(["word"] * n_filler_words)
    return {
        "title": "Three habits of disciplined traders",
        "hook": "Most traders lose money for one simple reason.",
        "lines": [
            "They trade on emotion instead of a plan.",
            f"Discipline beats intelligence every single time. {filler}".strip(),
        ],
        "cta": "Follow for more no-nonsense trading tips.",
        "description": "A short breakdown of trading discipline. Presenter is AI-generated.",
        "tags": ["trading", "discipline", "finance"],
    }


def test_validate_script_json_happy_path():
    payload = _valid_payload()
    raw = json.dumps(payload)
    script = validate_script_json(raw, target_seconds=15)
    assert isinstance(script, ScriptOutput)
    assert script.title == payload["title"]


def test_validate_script_json_rejects_invalid_json():
    with pytest.raises(ScriptGenerationError):
        validate_script_json("not json at all", target_seconds=15)


def test_validate_script_json_rejects_missing_fields():
    payload = _valid_payload()
    del payload["cta"]
    with pytest.raises(ScriptGenerationError):
        validate_script_json(json.dumps(payload), target_seconds=15)


def test_validate_script_json_rejects_long_hook():
    payload = _valid_payload()
    payload["hook"] = " ".join(["word"] * 20)
    with pytest.raises(ScriptGenerationError):
        validate_script_json(json.dumps(payload), target_seconds=15)


def test_validate_script_json_rejects_wrong_word_count():
    payload = _valid_payload()
    payload["lines"] = ["short."]
    # target_seconds=120 needs far more words than this tiny script has.
    with pytest.raises(ScriptGenerationError):
        validate_script_json(json.dumps(payload), target_seconds=120)


def test_validate_script_json_handles_markdown_fences():
    payload = _valid_payload()
    raw = "```json\n" + json.dumps(payload) + "\n```"
    script = validate_script_json(raw, target_seconds=15)
    assert script.hook == payload["hook"]


def test_target_word_range_scales_with_seconds():
    lo35, hi35 = target_word_range(35)
    lo70, hi70 = target_word_range(70)
    assert lo70 > lo35
    assert hi70 > hi35


def test_script_from_plain_text_single_paragraph():
    text = "This grabs attention fast. Here is a supporting fact. Another fact follows. Please subscribe now."
    script = script_from_plain_text(text, topic="my topic")
    assert script.hook.startswith("This grabs attention")
    assert script.cta == "Please subscribe now."
    assert len(script.lines) >= 1


def test_script_from_plain_text_multiline():
    text = "Hook line here\nMiddle line one\nMiddle line two\nClosing line here"
    script = script_from_plain_text(text)
    assert script.hook == "Hook line here"
    assert script.cta == "Closing line here"
    assert script.lines == ["Middle line one", "Middle line two"]


def test_script_from_plain_text_empty_raises():
    with pytest.raises(ScriptGenerationError):
        script_from_plain_text("   ")
