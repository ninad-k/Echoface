"""Typer CLI: make, batch, resume, doctor, clean."""

from __future__ import annotations

from datetime import date
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
            console.print(
                "\n[yellow]What to do next:[/]\n"
                f"  - New presenter? Run: [bold]echoface presenter init {cfg.presenter}[/] "
                "to scaffold assets/portraits/<name>/meta.yaml, then add your real consent "
                "document under consent/ and a portrait/idle clip.\n"
                "  - Just trying Echoface out? Use the bundled demo presenter instead: "
                "[bold]--presenter smoketest --config tests/fixtures/dummy.yaml[/] "
                "(no GPU, no consent subject - synthetic placeholder only).\n"
                "  - Full guide: docs/security/responsible-use-consent-policy.md and "
                "docs/user-manual.md."
            )
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


@app.command()
def prune(
    older_than: str | None = typer.Option(
        None, help="e.g. '30d', '12h'. Defaults to config's prune.older_than (30d)."
    ),
    keep_final: bool | None = typer.Option(
        None,
        help="Keep final.mp4/metadata.json, remove only intermediates. Defaults to config's prune.keep_final (true).",
    ),
    delete: bool = typer.Option(
        False,
        "--delete",
        help="Actually delete. Without this flag, prune only lists what it would remove (dry run).",
    ),
    root: Path = typer.Option(OUTPUT_ROOT, help="Output root to scan."),
    config: Path | None = typer.Option(None, "--config"),
):
    """List (dry run) or delete old job output directories to reclaim
    disk space. Deletion always requires the explicit --delete flag."""
    from echoface.prune import apply_prune, find_prune_candidates, format_size, parse_duration

    cfg = load_config(config)
    older_than_str = older_than or cfg.prune.older_than
    keep_final_val = cfg.prune.keep_final if keep_final is None else keep_final
    try:
        threshold = parse_duration(older_than_str)
    except ValueError as exc:
        console.print(f"[bold red]Error:[/] {exc}")
        raise typer.Exit(code=1) from exc

    candidates = find_prune_candidates(root, threshold, keep_final_val)
    if not candidates:
        console.print(f"Nothing to prune (older than {older_than_str} under {root}).")
        return

    table = Table(
        title=f"{'Would prune' if not delete else 'Pruning'} (older than {older_than_str}, keep_final={keep_final_val})"
    )
    table.add_column("Job")
    table.add_column("Age")
    table.add_column("Files")
    table.add_column("Size")
    total_size = 0
    for c in candidates:
        table.add_row(
            c.job_id,
            f"{c.age.days}d" if c.age else "unknown",
            str(len(c.files_to_remove)),
            format_size(c.size_bytes),
        )
        total_size += c.size_bytes
    console.print(table)
    console.print(f"Total: {len(candidates)} job(s), {format_size(total_size)}")

    if not delete:
        console.print(
            "\n[yellow]Dry run — nothing deleted. Re-run with --delete to actually remove these.[/]"
        )
        return

    freed = apply_prune(candidates)
    console.print(f"[bold green]Freed {format_size(freed)}.[/]")


presenter_app = typer.Typer(help="Manage presenter folders (assets/portraits/<name>/).")
app.add_typer(presenter_app, name="presenter")


@presenter_app.command("init")
def presenter_init(
    name: str = typer.Argument(..., help="Presenter folder name to create under assets/portraits/."),
    force: bool = typer.Option(False, help="Overwrite an existing meta.yaml."),
) -> None:
    """Scaffold a new presenter folder: assets/portraits/<name>/meta.yaml
    plus a README reminding you what else is needed. This does NOT create
    or weaken the consent gate - the scaffolded meta.yaml references a
    consent document that does not exist yet on purpose; `echoface make`
    will keep refusing to render this presenter until you add a real,
    signed one under consent/ and point consent_ref at it."""
    presenter_dir = Path("assets/portraits") / name
    meta_path = presenter_dir / "meta.yaml"
    if meta_path.exists() and not force:
        console.print(f"[bold red]Error:[/] {meta_path} already exists (use --force to overwrite).")
        raise typer.Exit(code=1)

    presenter_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    consent_ref = f"consent/{name}_{today}.pdf"
    meta_path.write_text(
        f"""# Presenter scaffolded by `echoface presenter init {name}`.
# Fill in display_name, then add a REAL signed consent document at the
# path below (see docs/security/responsible-use-consent-policy.md and
# consent/README.md for what it should contain) before this presenter
# can be rendered - echoface refuses to render without it, by design.
display_name: {name.replace("_", " ").replace("-", " ").title()}
consent_ref: {consent_ref}
consent_date: {today}
voice_consent: false
""",
        encoding="utf-8",
    )
    readme_path = presenter_dir / "README.md"
    if not readme_path.exists():
        readme_path.write_text(
            f"""# Presenter: {name}

Still needed before `echoface make --presenter {name}` will work:

1. **Consent.** Get written consent from the real person (or don't use a
   real person's likeness at all). Put the signed document at
   `{consent_ref}` (or update `meta.yaml`'s `consent_ref` to wherever you
   put it). See ../../../docs/security/responsible-use-consent-policy.md.
2. **A face.** Either:
   - `idle.mp4`: a short (10-20s) clip of the person sitting still and
     blinking naturally, front-facing, evenly lit, mouth closed - used by
     `face.engine: wav2lip` (default); or
   - `portrait.png`/`.jpg`: a single sharp, front-facing, well-lit photo
     (>=1024px), used by `face.engine: sadtalker` or as a wav2lip fallback
     when no idle.mp4 is present.
3. Edit `meta.yaml`'s `display_name` to something readable.

Then: `echoface doctor` should show this presenter's consent as OK, and
`echoface make --topic "..." --presenter {name}` will work.
""",
            encoding="utf-8",
        )

    console.print(f"[bold green]Scaffolded:[/] {presenter_dir}/ (meta.yaml, README.md)")
    console.print(
        f"[yellow]Next:[/] add a real signed consent document at [bold]{consent_ref}[/] "
        f"and an idle.mp4/portrait.png under {presenter_dir}/ - see {presenter_dir}/README.md."
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
