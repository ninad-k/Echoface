"""`echoface prune`: delete old job output directories to reclaim disk
space (output/<job-id>/ accumulates indefinitely otherwise — see
docs/project/improvements-and-known-issues.md). Dry-run by default;
actual deletion requires an explicit flag, enforced at the CLI layer.
"""

from __future__ import annotations

import contextlib
import json
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

KEEP_FILES_WHEN_KEEP_FINAL = {"final.mp4", "metadata.json", "job.json"}

_DURATION_RE = re.compile(r"^(\d+)\s*([dhm])$", re.IGNORECASE)
_UNIT_SECONDS = {"d": 86400, "h": 3600, "m": 60}


def parse_duration(text: str) -> timedelta:
    """Parse a simple duration string like '30d', '12h', '90m' into a
    timedelta. Raises ValueError on anything else (deliberately narrow —
    this is a CLI flag, not a general duration parser)."""
    match = _DURATION_RE.match(text.strip())
    if not match:
        raise ValueError(f"invalid duration {text!r}; expected e.g. '30d', '12h', '90m'")
    amount, unit = match.groups()
    return timedelta(seconds=int(amount) * _UNIT_SECONDS[unit.lower()])


@dataclass
class JobPruneInfo:
    job_dir: Path
    job_id: str
    created_at: datetime | None
    age: timedelta | None
    size_bytes: int
    files_to_remove: list[Path]
    would_keep_final: bool


def _job_created_at(job_dir: Path) -> datetime | None:
    job_json = job_dir / "job.json"
    if job_json.exists():
        try:
            data = json.loads(job_json.read_text(encoding="utf-8"))
            raw = data.get("created_at")
            if raw:
                return datetime.fromisoformat(raw)
        except (json.JSONDecodeError, ValueError):
            pass
    try:
        return datetime.fromtimestamp(job_dir.stat().st_mtime, tz=UTC)
    except OSError:
        return None


def _dir_size(path: Path) -> int:
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            with contextlib.suppress(OSError):
                total += f.stat().st_size
    return total


def find_prune_candidates(
    output_root: Path,
    older_than: timedelta,
    keep_final: bool,
    now: datetime | None = None,
) -> list[JobPruneInfo]:
    """List every job under `output_root` older than `older_than`, with
    what would be removed for each (pure/dry — does not touch the
    filesystem). `keep_final` controls whether final.mp4/metadata.json
    are excluded from the removal list (freeing intermediate artifacts
    only) or the whole job dir is slated for removal."""
    now = now or datetime.now(UTC)
    if not output_root.exists():
        return []

    candidates = []
    for job_dir in sorted(output_root.iterdir()):
        if not job_dir.is_dir():
            continue
        created_at = _job_created_at(job_dir)
        age = (now - created_at) if created_at else None
        if age is None or age < older_than:
            continue

        if keep_final:
            files_to_remove = [
                f for f in job_dir.rglob("*") if f.is_file() and f.name not in KEEP_FILES_WHEN_KEEP_FINAL
            ]
        else:
            files_to_remove = [f for f in job_dir.rglob("*") if f.is_file()]

        size = sum(f.stat().st_size for f in files_to_remove if f.exists())
        candidates.append(
            JobPruneInfo(
                job_dir=job_dir,
                job_id=job_dir.name,
                created_at=created_at,
                age=age,
                size_bytes=size,
                files_to_remove=files_to_remove,
                would_keep_final=keep_final,
            )
        )
    return candidates


def apply_prune(candidates: list[JobPruneInfo]) -> int:
    """Actually delete what `find_prune_candidates` identified. Returns
    the number of bytes freed. Caller (the CLI) is responsible for only
    calling this when the user passed an explicit deletion flag."""
    freed = 0
    for info in candidates:
        for f in info.files_to_remove:
            if f.exists():
                freed += f.stat().st_size
                f.unlink()
        if not info.would_keep_final:
            # Remove the (now-empty, or never-had-final) job directory
            # entirely rather than leaving an empty shell behind.
            shutil.rmtree(info.job_dir, ignore_errors=True)
        else:
            # Clean up now-empty subdirectories (e.g. left over from
            # intermediate artifacts), but keep the job dir itself since
            # final.mp4/metadata.json remain in it.
            for sub in sorted(info.job_dir.rglob("*"), reverse=True):
                if sub.is_dir() and not any(sub.iterdir()):
                    sub.rmdir()
    return freed


def format_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"
