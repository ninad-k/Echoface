"""Captions stage: voice.wav -> words.json + captions.ass.

Uses faster-whisper (imported lazily so unit tests / environments without
it installed still work) for word-level timestamps, then aligns the
recognised words back to the known script text (which is authoritative for
spelling) via difflib, and finally emits an ASS file with 2-3 words per
event and the currently-spoken word highlighted via karaoke (\\k) tags.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from echoface.stages.base import Stage
from echoface.util import ffmpeg as ffm


@dataclass
class Word:
    text: str
    start: float
    end: float
    line_id: int = 0


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", text)


def canonical_words(script: dict) -> list[str]:
    parts = [script["hook"], *script.get("lines", []), script["cta"]]
    words: list[str] = []
    for part in parts:
        words.extend(_tokenize(part))
    return words


def canonical_word_line_ids(script: dict) -> list[int]:
    """Parallel array to canonical_words(): which source line (hook=0,
    lines[0]=1, ..., cta=last) each word belongs to. Used so caption groups
    never splice the tail of one sentence onto the head of the next (e.g.
    "...always." + "Use stop-losses..." reading as "plan always Use")."""
    parts = [script["hook"], *script.get("lines", []), script["cta"]]
    line_ids: list[int] = []
    for i, part in enumerate(parts):
        line_ids.extend([i] * len(_tokenize(part)))
    return line_ids


def transcribe_words(
    wav_path: Path, model_size: str = "small", device: str = "cpu", compute_type: str = "int8"
) -> list[Word]:
    """Run faster-whisper with word timestamps. Imported lazily: raises a
    clear ImportError-derived message if the optional dependency isn't
    installed, instead of failing at module import time."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise RuntimeError(
            "faster-whisper is not installed. Install the 'captions' extra "
            "(pip install -e .[captions]) to run the real captions stage."
        ) from exc

    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments, _info = model.transcribe(str(wav_path), word_timestamps=True)
    words: list[Word] = []
    for seg in segments:
        for w in seg.words or []:
            words.append(Word(text=w.word.strip(), start=w.start, end=w.end))
    return words


def align_words_to_script(
    recognised: list[Word], script_words: list[str], script_line_ids: list[int] | None = None
) -> list[Word]:
    """Align faster-whisper's recognised words to the known-correct script
    words using difflib's SequenceMatcher, replacing recognised spelling
    with the canonical script spelling wherever they match up, so that
    e.g. misheard names/technical terms show the right text while keeping
    Whisper's timestamps.

    Recognised words that don't align to anything are dropped only if there
    are more recognised words than script words in that region (extra
    filler); script words with no aligned recognised word are skipped
    (we only caption words we have timing for).

    If script_line_ids is given (parallel to script_words, from
    canonical_word_line_ids), each output Word also carries which source
    line it came from, so callers can avoid grouping captions across a
    sentence boundary.
    """
    rec_norm = [w.text.lower().strip(".,!?;:\"'") for w in recognised]
    script_norm = [w.lower() for w in script_words]

    def line_id_for(j: int) -> int:
        if script_line_ids and 0 <= j < len(script_line_ids):
            return script_line_ids[j]
        return 0

    matcher = difflib.SequenceMatcher(a=rec_norm, b=script_norm, autojunk=False)
    aligned: list[Word] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                rec = recognised[i1 + k]
                canon = script_words[j1 + k]
                aligned.append(Word(text=canon, start=rec.start, end=rec.end, line_id=line_id_for(j1 + k)))
        elif tag == "replace":
            # Best-effort 1:1 pairing over the shorter span; keep timestamps,
            # swap in canonical spelling.
            span = min(i2 - i1, j2 - j1)
            for k in range(span):
                rec = recognised[i1 + k]
                canon = script_words[j1 + k]
                aligned.append(Word(text=canon, start=rec.start, end=rec.end, line_id=line_id_for(j1 + k)))
            # Leftover recognised words beyond the script span: keep as-is
            # (better to caption something than drop time silently), tagged
            # with the last known line so they don't merge into the next.
            tail_line_id = line_id_for(j1 + span - 1) if span else line_id_for(j1)
            for k in range(span, i2 - i1):
                rec = recognised[i1 + k]
                aligned.append(Word(text=rec.text, start=rec.start, end=rec.end, line_id=tail_line_id))
        # tag == "delete": recognised words with nothing to align to are
        # dropped only implicitly (not appended) — none here since delete
        # means recognised has extra content not in script; we still want
        # timing continuity, so keep them verbatim.
        elif tag == "delete":
            tail_line_id = line_id_for(j1 - 1) if j1 > 0 else 0
            for k in range(i2 - i1):
                rec = recognised[i1 + k]
                aligned.append(Word(text=rec.text, start=rec.start, end=rec.end, line_id=tail_line_id))
        # tag == "insert": script words with no recognised counterpart —
        # nothing to time, so we skip them.
    return aligned


def generate_dummy_words(
    script_words: list[str], total_duration_s: float, script_line_ids: list[int] | None = None
) -> list[Word]:
    """No-ML fallback for the captions stage: evenly distribute the known
    script words across the audio's total duration. Used by
    ``captions.engine: dummy`` for smoke tests / environments without
    faster-whisper's model weights (which require a network download).
    """
    n = len(script_words)
    if n == 0 or total_duration_s <= 0:
        return []
    per_word = total_duration_s / n
    words = []
    for i, w in enumerate(script_words):
        start = i * per_word
        end = start + per_word * 0.9  # small gap before next word
        line_id = script_line_ids[i] if script_line_ids and i < len(script_line_ids) else 0
        words.append(Word(text=w, start=start, end=end, line_id=line_id))
    return words


def group_words(words: list[Word], max_words_per_line: int = 3) -> list[list[Word]]:
    """Group words into 2-3 word caption events, never spanning a source
    line boundary (Word.line_id) so a caption never splices the tail of one
    sentence onto the head of the next (e.g. "...always." + "Use ..." would
    otherwise read as one nonsensical group)."""
    groups: list[list[Word]] = []
    current: list[Word] = []
    for w in words:
        if current and (len(current) >= max_words_per_line or w.line_id != current[-1].line_id):
            groups.append(current)
            current = []
        current.append(w)
    if current:
        groups.append(current)
    return groups


def _fmt_ass_time(t: float) -> str:
    t = max(t, 0.0)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


ASS_HEADER_TEMPLATE = """[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font},{font_size},&H00FFFFFF,&H000080FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,60,60,180,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def build_ass(
    words: list[Word],
    *,
    width: int = 1080,
    height: int = 1920,
    font: str = "Arial",
    font_size: int = 96,
    max_words_per_line: int = 3,
) -> str:
    """Emit an ASS subtitle file, 2-3 words per event, with the currently
    spoken word highlighted via a karaoke (\\k) effect: each word gets a
    \\k<centiseconds> tag with the highlight colour, so players/burn-in
    render a per-word highlight sweep across the group.
    """
    header = ASS_HEADER_TEMPLATE.format(width=width, height=height, font=font, font_size=font_size)
    lines = [header]
    groups = group_words(words, max_words_per_line)
    for group in groups:
        if not group:
            continue
        start = group[0].start
        end = group[-1].end
        text_parts = []
        for w in group:
            dur_cs = max(int(round((w.end - w.start) * 100)), 1)
            # \k tag: highlight colour swept in over the word's duration.
            text_parts.append(f"{{\\k{dur_cs}}}{w.text}")
        text = r"\N".join([" ".join(text_parts)]) if False else " ".join(text_parts)
        lines.append(f"Dialogue: 0,{_fmt_ass_time(start)},{_fmt_ass_time(end)},Caption,,0,0,0,,{text}")
    return "\n".join(lines) + "\n"


class CaptionsStage(Stage):
    name = "captions"

    def inputs(self) -> list[Path]:
        return [self.job.path_for("voice.wav"), self.job.path_for("script.json")]

    def outputs(self) -> list[Path]:
        return [self.job.path_for("words.json"), self.job.path_for("captions.ass")]

    def run(self) -> None:
        wav_path = self.job.path_for("voice.wav")
        script_path = self.job.path_for("script.json")
        with open(script_path, encoding="utf-8") as fh:
            script = json.load(fh)

        cap_cfg = self.cfg.captions
        script_words = canonical_words(script)
        script_line_ids = canonical_word_line_ids(script)
        if cap_cfg.engine == "dummy":
            total_duration = ffm.probe(wav_path).duration_s
            aligned = generate_dummy_words(script_words, total_duration, script_line_ids)
        else:
            recognised = transcribe_words(wav_path, cap_cfg.model, cap_cfg.device, cap_cfg.compute_type)
            aligned = align_words_to_script(recognised, script_words, script_line_ids)

        words_path = self.job.path_for("words.json")
        words_path.parent.mkdir(parents=True, exist_ok=True)
        with open(words_path, "w", encoding="utf-8") as fh:
            json.dump([{"text": w.text, "start": w.start, "end": w.end} for w in aligned], fh, indent=2)

        ass_text = build_ass(
            aligned,
            width=self.cfg.compose.width,
            height=self.cfg.compose.height,
            font=cap_cfg.font,
            font_size=cap_cfg.font_size,
            max_words_per_line=cap_cfg.max_words_per_line,
        )
        ass_path = self.job.path_for("captions.ass")
        ass_path.write_text(ass_text, encoding="utf-8")
