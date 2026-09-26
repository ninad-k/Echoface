import pytest

from echoface.stages.captions import (
    Word,
    align_words_to_script,
    build_ass,
    canonical_words,
    generate_dummy_words,
    group_words,
)


def test_canonical_words():
    script = {
        "hook": "Most traders lose money.",
        "lines": ["Discipline beats intelligence."],
        "cta": "Follow for more.",
    }
    words = canonical_words(script)
    assert words == [
        "Most",
        "traders",
        "lose",
        "money",
        "Discipline",
        "beats",
        "intelligence",
        "Follow",
        "for",
        "more",
    ]


def test_align_words_to_script_fixes_misrecognition():
    # Whisper misheard "traders" as "traiders" and lowercased everything.
    recognised = [
        Word("most", 0.0, 0.3),
        Word("traiders", 0.3, 0.8),
        Word("lose", 0.8, 1.0),
        Word("money", 1.0, 1.4),
    ]
    script_words = ["Most", "traders", "lose", "money"]
    aligned = align_words_to_script(recognised, script_words)
    assert [w.text for w in aligned] == ["Most", "traders", "lose", "money"]
    # Timestamps preserved from the recognised words.
    assert aligned[1].start == 0.3
    assert aligned[1].end == 0.8


def test_align_words_exact_match():
    recognised = [Word("hello", 0.0, 0.5), Word("world", 0.5, 1.0)]
    script_words = ["hello", "world"]
    aligned = align_words_to_script(recognised, script_words)
    assert [w.text for w in aligned] == ["hello", "world"]


def test_group_words_into_two_or_three():
    words = [Word(str(i), i, i + 0.5) for i in range(7)]
    groups = group_words(words, max_words_per_line=3)
    assert [len(g) for g in groups] == [3, 3, 1]


def test_group_words_never_spans_a_line_boundary():
    # Reproduces a real bug found in end-to-end testing: without line-aware
    # grouping, the tail of one sentence ("...plan, always.") got merged
    # with the head of the next ("Use stop-losses...") into one caption
    # event reading "plan always Use" — correct chronologically, but
    # nonsensical on screen because it crosses a sentence boundary.
    words = [
        Word("plan", 4.1, 4.48, line_id=1),
        Word("always", 4.76, 5.12, line_id=1),
        Word("Use", 5.86, 6.02, line_id=2),
        Word("stop", 6.02, 6.22, line_id=2),
        Word("losses", 6.22, 6.64, line_id=2),
    ]
    groups = group_words(words, max_words_per_line=3)
    texts = [[w.text for w in g] for g in groups]
    assert texts == [["plan", "always"], ["Use", "stop", "losses"]]


def test_canonical_word_line_ids_matches_canonical_words_length():
    from echoface.stages.captions import canonical_word_line_ids

    script = {
        "hook": "Most traders lose money.",
        "lines": ["Discipline beats intelligence.", "Plan your trades."],
        "cta": "Follow for more.",
    }
    words = canonical_words(script)
    line_ids = canonical_word_line_ids(script)
    assert len(words) == len(line_ids)
    # hook=0, lines[0]=1, lines[1]=2, cta=3
    assert line_ids == [0, 0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3]


def test_build_ass_contains_header_and_karaoke_tags():
    words = [
        Word("Most", 0.0, 0.3),
        Word("traders", 0.3, 0.8),
        Word("lose", 0.8, 1.1),
    ]
    ass_text = build_ass(words, max_words_per_line=3)
    assert "[Script Info]" in ass_text
    assert "[V4+ Styles]" in ass_text
    assert "[Events]" in ass_text
    assert "Dialogue:" in ass_text
    # Karaoke highlight tag present for per-word timing.
    assert r"\k" in ass_text
    assert "Most" in ass_text and "traders" in ass_text and "lose" in ass_text


def test_generate_dummy_words_covers_duration_evenly():
    words = generate_dummy_words(["one", "two", "three", "four"], total_duration_s=8.0)
    assert [w.text for w in words] == ["one", "two", "three", "four"]
    assert words[0].start == 0.0
    assert words[-1].end <= 8.0
    # Roughly evenly spaced.
    assert words[1].start == pytest.approx(2.0)


def test_generate_dummy_words_empty_inputs():
    assert generate_dummy_words([], 10.0) == []
    assert generate_dummy_words(["a"], 0.0) == []


def test_build_ass_multiple_events_for_long_word_list():
    words = [Word(f"w{i}", i * 0.3, i * 0.3 + 0.25) for i in range(9)]
    ass_text = build_ass(words, max_words_per_line=3)
    dialogue_lines = [ln for ln in ass_text.splitlines() if ln.startswith("Dialogue:")]
    assert len(dialogue_lines) == 3
