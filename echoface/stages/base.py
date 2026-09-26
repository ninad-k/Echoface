"""Common Stage interface.

Every pipeline stage (script, voice, face, captions, compose) implements
this interface so the CLI / runner can treat them uniformly: check
``is_done()`` to decide whether to skip, otherwise call ``run()``.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from pathlib import Path

from echoface.config import EchofaceConfig, stage_hash
from echoface.job import Job


class Stage(ABC):
    name: str = "stage"

    def __init__(self, job: Job, cfg: EchofaceConfig, logger=None):
        self.job = job
        self.cfg = cfg
        self.logger = logger

    # ---- interface ----------------------------------------------------
    @abstractmethod
    def inputs(self) -> list[Path]:
        """Paths this stage reads (from prior stages)."""

    @abstractmethod
    def outputs(self) -> list[Path]:
        """Paths this stage must produce for it to be considered done."""

    def extra_hash_inputs(self) -> dict | None:
        """Stage-specific values that should also invalidate the cache when
        changed (e.g. the topic text for the script stage). None by default.
        """
        return None

    @abstractmethod
    def run(self) -> None:
        """Do the actual work. Must create all paths from outputs()."""

    # ---- shared behaviour ----------------------------------------------
    def current_hash(self) -> str:
        return stage_hash(self.cfg, self.name, self.extra_hash_inputs())

    def is_done(self) -> bool:
        return self.job.is_stage_done(self.name, self.current_hash(), self.outputs())

    def execute(self, force: bool = False) -> float:
        """Run the stage unless already done, recording timing/status in the
        job. Returns the duration in seconds (0.0 if skipped)."""
        if not force and self.is_done():
            if self.logger:
                self.logger.info(f"[{self.name}] up to date, skipping")
            return 0.0

        if self.logger:
            self.logger.info(f"[{self.name}] running...")
        self.job.mark_started(self.name)
        start = time.monotonic()
        try:
            self.run()
        except Exception as exc:
            self.job.mark_failed(self.name, str(exc))
            raise
        duration = time.monotonic() - start
        missing = [p for p in self.outputs() if not p.exists()]
        if missing:
            err = f"stage {self.name!r} did not produce expected outputs: {missing}"
            self.job.mark_failed(self.name, err)
            raise RuntimeError(err)
        self.job.mark_done(self.name, self.current_hash(), duration)
        if self.logger:
            self.logger.info(f"[{self.name}] done in {duration:.1f}s")
        return duration
