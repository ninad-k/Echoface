"""Job folder + job.json state management: stage status tracking, skip
logic (idempotency via config hash), and clean/invalidate-downstream.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

STAGE_ORDER = ["script", "voice", "face", "captions", "compose"]

OUTPUT_ROOT = Path("output")


class ConsentError(RuntimeError):
    """Raised when a presenter's consent metadata is missing/invalid."""


def slugify(text: str, max_len: int = 40) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    if not text:
        text = "job"
    return text[:max_len].rstrip("-")


def make_job_id(topic: str, now: datetime | None = None) -> str:
    now = now or datetime.now()
    return f"{now.strftime('%Y%m%d-%H%M')}_{slugify(topic)}"


@dataclass
class StageStatus:
    status: str = "pending"  # pending | done | failed
    config_hash: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_s: float | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "config_hash": self.config_hash,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_s": self.duration_s,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> StageStatus:
        return cls(
            status=data.get("status", "pending"),
            config_hash=data.get("config_hash"),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            duration_s=data.get("duration_s"),
            error=data.get("error"),
        )


@dataclass
class Job:
    job_id: str
    root: Path
    topic: str | None = None
    script_file: str | None = None
    presenter: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    stages: dict[str, StageStatus] = field(default_factory=dict)

    @property
    def job_dir(self) -> Path:
        return self.root / self.job_id

    @property
    def json_path(self) -> Path:
        return self.job_dir / "job.json"

    @property
    def run_log_path(self) -> Path:
        return self.job_dir / "run.log"

    def path_for(self, filename: str) -> Path:
        return self.job_dir / filename

    def ensure_dir(self) -> None:
        self.job_dir.mkdir(parents=True, exist_ok=True)

    def save(self) -> None:
        self.ensure_dir()
        data = {
            "job_id": self.job_id,
            "topic": self.topic,
            "script_file": self.script_file,
            "presenter": self.presenter,
            "created_at": self.created_at,
            "stages": {name: st.to_dict() for name, st in self.stages.items()},
        }
        with open(self.json_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    @classmethod
    def load(cls, job_id: str, root: Path = OUTPUT_ROOT) -> Job:
        job_dir = root / job_id
        json_path = job_dir / "job.json"
        if not json_path.exists():
            raise FileNotFoundError(f"no job.json found for job {job_id!r} at {json_path}")
        with open(json_path, encoding="utf-8") as fh:
            data = json.load(fh)
        stages = {name: StageStatus.from_dict(st) for name, st in data.get("stages", {}).items()}
        return cls(
            job_id=data["job_id"],
            root=root,
            topic=data.get("topic"),
            script_file=data.get("script_file"),
            presenter=data.get("presenter"),
            created_at=data.get("created_at", datetime.now(UTC).isoformat()),
            stages=stages,
        )

    @classmethod
    def create(
        cls,
        topic: str | None,
        root: Path = OUTPUT_ROOT,
        script_file: str | None = None,
        presenter: str | None = None,
        job_id: str | None = None,
    ) -> Job:
        """Create a new job, OR — if job_id is given and a job.json already
        exists at that path — load and return the existing job so its stage
        statuses (and therefore idempotent skip behaviour) are preserved.

        Without this, re-running `echoface make --job-id <existing>` would
        silently overwrite job.json with a blank one and redo every stage
        from scratch, defeating the whole is_stage_done()/config-hash skip
        mechanism for that (very common) re-run path — this was caught by
        real end-to-end testing where `make` was re-invoked with the same
        --job-id and unexpectedly re-ran a ~2 minute GPU face stage.
        """
        if job_id:
            existing_path = root / job_id / "job.json"
            if existing_path.exists():
                job = cls.load(job_id, root=root)
                # Keep the job's original topic/script_file/presenter
                # unless the caller is explicitly changing them.
                if topic is not None:
                    job.topic = topic
                if script_file is not None:
                    job.script_file = script_file
                if presenter is not None:
                    job.presenter = presenter
                job.save()
                return job

        jid = job_id or make_job_id(topic or (script_file or "job"))
        job = cls(job_id=jid, root=root, topic=topic, script_file=script_file, presenter=presenter)
        job.ensure_dir()
        job.save()
        return job

    def status_for(self, stage_name: str) -> StageStatus:
        return self.stages.setdefault(stage_name, StageStatus())

    def mark_started(self, stage_name: str) -> None:
        st = self.status_for(stage_name)
        st.status = "running"
        st.started_at = datetime.now(UTC).isoformat()
        st.error = None
        self.save()

    def mark_done(self, stage_name: str, config_hash: str, duration_s: float) -> None:
        st = self.status_for(stage_name)
        st.status = "done"
        st.config_hash = config_hash
        st.finished_at = datetime.now(UTC).isoformat()
        st.duration_s = duration_s
        st.error = None
        self.save()

    def mark_failed(self, stage_name: str, error: str) -> None:
        st = self.status_for(stage_name)
        st.status = "failed"
        st.finished_at = datetime.now(UTC).isoformat()
        st.error = error
        self.save()

    def is_stage_done(self, stage_name: str, current_hash: str, outputs: list[Path]) -> bool:
        """A stage is considered done (skippable) iff its recorded status is
        'done', the config hash matches the current one, and every declared
        output file still exists on disk."""
        st = self.stages.get(stage_name)
        if st is None or st.status != "done":
            return False
        if st.config_hash != current_hash:
            return False
        return all(p.exists() for p in outputs)

    def clean_from(self, stage_name: str) -> list[str]:
        """Invalidate `stage_name` and every downstream stage: reset their
        status to pending and delete their output files. Returns the list
        of stage names that were invalidated."""
        if stage_name not in STAGE_ORDER:
            raise ValueError(f"unknown stage {stage_name!r}, expected one of {STAGE_ORDER}")
        idx = STAGE_ORDER.index(stage_name)
        to_clean = STAGE_ORDER[idx:]
        for name in to_clean:
            if name in self.stages:
                self.stages[name] = StageStatus()
        self.save()
        return to_clean


def check_presenter_consent(presenter: str, assets_root: Path = Path("assets/portraits")) -> dict:
    """Validate a presenter's meta.yaml + consent_ref. Raises ConsentError
    on any problem. Returns the parsed meta dict on success."""
    import yaml

    presenter_dir = assets_root / presenter
    meta_path = presenter_dir / "meta.yaml"
    if not presenter_dir.exists():
        raise ConsentError(f"presenter {presenter!r} not found at {presenter_dir}")
    if not meta_path.exists():
        raise ConsentError(f"presenter {presenter!r} is missing meta.yaml at {meta_path}")
    with open(meta_path, encoding="utf-8") as fh:
        meta = yaml.safe_load(fh) or {}
    consent_ref = meta.get("consent_ref")
    if not consent_ref:
        raise ConsentError(f"presenter {presenter!r} has no consent_ref in {meta_path}; refusing to render")
    consent_path = Path(consent_ref)
    if not consent_path.exists():
        raise ConsentError(
            f"presenter {presenter!r} consent_ref {consent_ref!r} does not exist on disk; "
            "refusing to render until written consent is provided"
        )
    return meta
