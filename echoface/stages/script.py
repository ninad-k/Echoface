"""Script stage: local LLM (Ollama) -> script.json, or --script-file to skip
the LLM entirely.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import requests
from pydantic import BaseModel, Field, ValidationError

from echoface.stages.base import Stage
from echoface.util.text import word_count

WORDS_PER_SECOND = 2.6


class ScriptOutput(BaseModel):
    title: str = Field(max_length=70)
    hook: str
    lines: list[str]
    cta: str
    description: str
    tags: list[str] = Field(default_factory=list)


class ScriptGenerationError(RuntimeError):
    pass


def target_word_range(target_seconds: int) -> tuple[int, int]:
    center = target_seconds * WORDS_PER_SECOND
    return int(center * 0.55), int(center * 1.6)


def spoken_word_count(script: ScriptOutput) -> int:
    parts = [script.hook, *script.lines, script.cta]
    return sum(word_count(p) for p in parts)


def hook_word_count_ok(hook: str, max_words: int = 12) -> bool:
    return word_count(hook) <= max_words


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    # Ollama with format=json should return pure JSON, but be defensive:
    # strip markdown code fences if a model added them anyway.
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"```$", "", raw).strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    candidate = match.group(0) if match else raw
    return json.loads(candidate)


def validate_script_json(raw: str, target_seconds: int) -> ScriptOutput:
    """Parse + validate the schema and the word-count budget. Raises
    ScriptGenerationError with a human-readable reason on failure (used to
    build the retry prompt hint)."""
    try:
        data = _extract_json(raw)
    except json.JSONDecodeError as exc:
        raise ScriptGenerationError(f"invalid JSON: {exc}") from exc

    try:
        script = ScriptOutput.model_validate(data)
    except ValidationError as exc:
        raise ScriptGenerationError(f"schema validation failed: {exc}") from exc

    if not hook_word_count_ok(script.hook):
        raise ScriptGenerationError(f"hook has {word_count(script.hook)} words, must be <= 12")

    lo, hi = target_word_range(target_seconds)
    total = spoken_word_count(script)
    if not (lo <= total <= hi):
        raise ScriptGenerationError(
            f"spoken word count {total} outside target range [{lo}, {hi}] for target_seconds={target_seconds}"
        )
    return script


def render_prompt(template_path: Path, topic: str, target_seconds: int) -> str:
    template = template_path.read_text(encoding="utf-8")
    lo, hi = target_word_range(target_seconds)
    mid = (lo + hi) // 2
    # ~8 words/line average (short, speakable sentences) minus the hook/cta.
    suggested_lines = max(3, round(mid / 8) - 1)
    return (
        template.replace("{{topic}}", topic)
        .replace("{{target_seconds}}", str(target_seconds))
        .replace("{{min_words}}", str(lo))
        .replace("{{max_words}}", str(hi))
        .replace("{{mid_words}}", str(mid))
        .replace("{{suggested_lines}}", str(suggested_lines))
    )


def call_ollama(host: str, model: str, prompt: str, temperature: float, timeout: float = 120.0) -> str:
    resp = requests.post(
        f"{host.rstrip('/')}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {"temperature": temperature},
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("response", "")


def script_from_plain_text(text: str, topic: str | None = None) -> ScriptOutput:
    """Build a ScriptOutput from a plain text file (skips the LLM)."""
    # Split on blank lines / sentence-ish boundaries.
    raw_lines = [ln.strip() for ln in re.split(r"\n+", text.strip()) if ln.strip()]
    if not raw_lines:
        raise ScriptGenerationError("script file is empty")
    if len(raw_lines) == 1:
        # Single block of text: split into sentences.
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", raw_lines[0]) if s.strip()]
        raw_lines = sentences or raw_lines
    hook = raw_lines[0]
    cta = raw_lines[-1] if len(raw_lines) > 1 else "Thanks for watching."
    middle = raw_lines[1:-1] if len(raw_lines) > 2 else (raw_lines[1:] if len(raw_lines) > 1 else [])
    title = (topic or hook)[:70]
    description = f"{title}. Presenter is AI-generated."
    return ScriptOutput(
        title=title,
        hook=hook,
        lines=middle or [hook],
        cta=cta,
        description=description,
        tags=[],
    )


class ScriptStage(Stage):
    name = "script"

    def __init__(self, job, cfg, logger=None, topic: str | None = None, script_file: Path | None = None):
        super().__init__(job, cfg, logger)
        self.topic = topic
        self.script_file = script_file

    def inputs(self) -> list[Path]:
        return [self.script_file] if self.script_file else []

    def outputs(self) -> list[Path]:
        return [self.job.path_for("script.json")]

    def extra_hash_inputs(self) -> dict | None:
        if self.script_file:
            return {
                "script_file": str(self.script_file),
                "mtime": self.script_file.stat().st_mtime if self.script_file.exists() else None,
            }
        return {"topic": self.topic}

    def run(self) -> None:
        sc = self.cfg.script
        script: ScriptOutput | None = None
        if self.script_file or sc.engine == "file":
            if not self.script_file:
                raise ScriptGenerationError("script.engine is 'file' but no --script-file was given")
            text = Path(self.script_file).read_text(encoding="utf-8")
            script = script_from_plain_text(text, topic=self.topic)
        else:
            if not self.topic:
                raise ScriptGenerationError("no --topic given and script.engine is 'ollama'")
            template_path = Path(sc.template)
            prompt = render_prompt(template_path, self.topic, self.cfg.target_seconds)
            last_error: str | None = None
            for attempt in range(1, sc.max_retries + 1):
                full_prompt = prompt
                if last_error:
                    full_prompt += (
                        f"\n\nYour previous attempt was rejected: {last_error}\n"
                        "If the reason was word count, you undershot — add more lines with "
                        "real substance (examples, numbers, brief explanations), do not just "
                        "pad existing lines. Try again, respond with ONLY the JSON object."
                    )
                if self.logger:
                    self.logger.info(f"[script] Ollama attempt {attempt}/{sc.max_retries}")
                raw = call_ollama(sc.host, sc.model, full_prompt, sc.temperature)
                try:
                    script = validate_script_json(raw, self.cfg.target_seconds)
                    break
                except ScriptGenerationError as exc:
                    last_error = str(exc)
                    if self.logger:
                        self.logger.warning(f"[script] attempt {attempt} rejected: {exc}")
            if script is None:
                raise ScriptGenerationError(
                    f"script generation failed after {sc.max_retries} attempts: {last_error}"
                )

        out_path = self.job.path_for("script.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(script.model_dump(), fh, indent=2)
