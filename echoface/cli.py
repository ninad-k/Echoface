"""Typer CLI: make, batch, resume, doctor, clean."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from echoface.config import EchofaceConfig, load_config
from echoface.doctor import run_doctor
from echoface.job import OUTPUT_ROOT, STAGE_ORDER, ConsentError, Job, check_presenter_consent
from echoface.stages.captions import CaptionsStage
from echoface.stages.compose import ComposeStage
from echoface.stages.face import FaceStage
from echoface.stages.script import ScriptStage
from echoface.stages.voice import VoiceStage
from echoface.util.env import load_env
from echoface.util.log import attach_job_log_file, detach_handler, get_logger

# Load .env (if present) before anything reads os.environ, so
# ECHOFACE_OLLAMA_HOST / HF_TOKEN / COQUI_TOS_AGREED etc. from a local
# .env take effect for every command below. No-op if .env is absent or
# python-dotenv isn't installed — everything still has a working default.
load_env()

app = typer.Typer(help="Echoface: local AI avatar video pipeline.")
console = Console()

STAGE_CLASSES = {
    "script": ScriptStage,
    "voice": VoiceStage,
    "face": FaceStage,
    "captions": CaptionsStage,
    "compose": ComposeStage,
}


def _build_overrides(presenter: str | None, seconds: int | None, monetized: bool | None) -> dict:
    overrides: dict = {}
    if presenter is not None:
        overrides["presenter"] = presenter
    if seconds is not None:
        overrides["target_seconds"] = seconds
    if monetized is not None:
        overrides["monetized"] = monetized
    return overrides


def _make_stage(stage_name: str, job: Job, cfg: EchofaceConfig, logger, *, topic=None, script_file=None):
    cls = STAGE_CLASSES[stage_name]
    if stage_name == "script":
        return cls(job, cfg, logger=logger, topic=topic, script_file=script_file)
    return cls(job, cfg, logger=logger)


def run_pipeline(
    job: Job,
    cfg: EchofaceConfig,
    *,
    topic: str | None = None,
    script_file: Path | None = None,
    until: str | None = None,
) -> list[tuple[str, float]]:
    logger = get_logger()
    file_handler = attach_job_log_file(logger, job.run_log_path)
    timings: list[tuple[str, float]] = []
    try:
        try:
            check_presenter_consent(cfg.presenter)
        except ConsentError as exc:
            console.print(f"[bold red]Consent check failed:[/] {exc}")
            raise typer.Exit(code=2) from exc

        stages_to_run = STAGE_ORDER
        if until:
            if until not in STAGE_ORDER:
                raise typer.BadParameter(f"--until must be one of {STAGE_ORDER}")
            stages_to_run = STAGE_ORDER[: STAGE_ORDER.index(until) + 1]

        for stage_name in stages_to_run:
            stage = _make_stage(stage_name, job, cfg, logger, topic=topic, script_file=script_file)
            duration = stage.execute()
            timings.append((stage_name, duration))
    finally:
        detach_handler(logger, file_handler)

    _print_timing_table(job.job_id, timings)
    return timings


def _print_timing_table(job_id: str, timings: list[tuple[str, float]]) -> None:
    table = Table(title=f"Echoface job {job_id} — stage timings")
    table.add_column("Stage")
    table.add_column("Duration", justify="right")
    total = 0.0
    for name, duration in timings:
        label = "skipped" if duration == 0.0 else f"{duration:.1f}s"
        table.add_row(name, label)
        total += duration
    table.add_row("total", f"{total:.1f}s", style="bold")
    console.print(table)


@app.command()
def make(
    topic: str | None = typer.Option(None, help="Video topic; the script stage prompts a local LLM with it."),
    script_file: Path | None = typer.Option(
        None, "--script-file", help="Plain-text script file; skips the LLM."
    ),
    presenter: str | None = typer.Option(None, help="Presenter name under assets/portraits/."),
    seconds: int | None = typer.Option(None, help="Target spoken duration in seconds."),
    until: str | None = typer.Option(None, help=f"Stop after this stage. One of: {', '.join(STAGE_ORDER)}."),
    config: Path | None = typer.Option(
        None, "--config", help="Path to echoface.yaml (default config/echoface.yaml)."
    ),
    monetized: bool | None = typer.Option(None, help="Override config.monetized."),
    job_id: str | None = typer.Option(None, help="Explicit job id (default: derived from topic/time)."),
):
    """Run the full pipeline (or up to --until) for a single topic/script."""
    if not topic and not script_file:
        console.print("[bold red]Error:[/] provide --topic or --script-file")
        raise typer.Exit(code=1)

    overrides = _build_overrides(presenter, seconds, monetized)
    cfg = load_config(config, overrides)

    job = Job.create(
        topic=topic,
        root=OUTPUT_ROOT,
        script_file=str(script_file) if script_file else None,
        presenter=cfg.presenter,
        job_id=job_id,
    )
    console.print(f"[bold green]Job:[/] {job.job_id}  ->  {job.job_dir}")
    run_pipeline(job, cfg, topic=topic, script_file=script_file, until=until)


@app.command()
def batch(
    file: Path = typer.Option(..., "--file", help="Text file, one topic per line."),
    presenter: str | None = typer.Option(None),
    seconds: int | None = typer.Option(None),
    config: Path | None = typer.Option(None, "--config"),
):
    """Run `make` once per line in a topics file."""
    if not file.exists():
        console.print(f"[bold red]Error:[/] topics file not found: {file}")
        raise typer.Exit(code=1)
    topics = [ln.strip() for ln in file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    console.print(f"[bold]Batch:[/] {len(topics)} topic(s) from {file}")
    overrides = _build_overrides(presenter, seconds, None)
    cfg = load_config(config, overrides)
    for i, topic in enumerate(topics, 1):
        console.print(f"\n[bold cyan]== ({i}/{len(topics)}) {topic}[/]")
        job = Job.create(topic=topic, root=OUTPUT_ROOT, presenter=cfg.presenter)
        try:
            run_pipeline(job, cfg, topic=topic)
        except Exception as exc:  # keep going with the rest of the batch
            console.print(f"[bold red]Job {job.job_id} failed:[/] {exc}")


@app.command()
def resume(
    job_id: str = typer.Argument(..., help="Job id under output/, e.g. 20260926-2130_three-habits."),
    config: Path | None = typer.Option(None, "--config"),
    until: str | None = typer.Option(None),
):
    """Resume a job: already-completed stages (matching config hash) are
    skipped automatically."""
    job = Job.load(job_id, root=OUTPUT_ROOT)
    cfg = load_config(config, {"presenter": job.presenter} if job.presenter else None)
    script_file = Path(job.script_file) if job.script_file else None
    console.print(f"[bold green]Resuming job:[/] {job.job_id}")
    run_pipeline(job, cfg, topic=job.topic, script_file=script_file, until=until)


@app.command()
def clean(
    job_id: str = typer.Argument(...),
    from_stage: str = typer.Option(
        ...,
        "--from",
        help=f"Invalidate this stage and everything downstream. One of: {', '.join(STAGE_ORDER)}.",
    ),
):
    """Invalidate a stage and all downstream stages for a job (resets
    job.json status; leaves files for you to delete or lets the next run
    overwrite them)."""
    job = Job.load(job_id, root=OUTPUT_ROOT)
    cleaned = job.clean_from(from_stage)
    stage_outputs = {
        "script": ["script.json"],
        "voice": ["voice.wav", "voice_16k.wav"],
        "face": ["face.mp4"],
        "captions": ["words.json", "captions.ass"],
        "compose": ["final.mp4", "metadata.json"],
    }
    for stage_name in cleaned:
        for fname in stage_outputs.get(stage_name, []):
            path = job.path_for(fname)
            if path.exists():
                path.unlink()
    console.print(f"[bold yellow]Cleaned stages:[/] {', '.join(cleaned)} for job {job_id}")


@app.command()
def doctor(
    config: Path | None = typer.Option(None, "--config"),
):
    """Print an environment/setup report. Never raises — every check is
    isolated and reported red/green."""
    cfg = load_config(config)
    checks = run_doctor(cfg)

    table = Table(title="Echoface doctor report")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    n_fail = 0
    for check in checks:
        if check.ok:
            status = "[bold green]OK[/]"
        elif check.level == "warning":
            status = "[bold yellow]WARN[/]"
        else:
            status = "[bold red]FAIL[/]"
            n_fail += 1
        table.add_row(check.name, status, check.detail)
    console.print(table)
    if n_fail:
        raise typer.Exit(code=1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
