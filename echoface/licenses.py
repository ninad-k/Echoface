"""Machine-readable model-licence table (models/licenses.yaml) and the
matching logic `echoface doctor` uses to warn about non-commercial models
selected in the active config while `monetized: true`.

Kept as its own module (rather than folded into doctor.py) so it's
independently unit-testable and so a future command (e.g. `echoface
licenses`) could reuse it without importing doctor's other checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_LICENSES_PATH = Path("models/licenses.yaml")


@dataclass
class ModelLicense:
    id: str
    name: str
    stage: str
    licence: str
    commercial: bool | str  # True | False | "check"
    source: str = ""
    note: str = ""
    match: dict[str, Any] = field(default_factory=dict)

    @property
    def is_commercial_safe(self) -> bool:
        return self.commercial is True

    @property
    def status_label(self) -> str:
        if self.commercial is True:
            return "commercial-ok"
        if self.commercial is False:
            return "non-commercial"
        return "unverified (check manually)"


def load_licenses(path: Path | None = None) -> list[ModelLicense]:
    """Parse models/licenses.yaml. Never raises on a missing/malformed
    file — returns an empty list instead, so `doctor` degrades gracefully
    (consistent with every other doctor check)."""
    path = path or DEFAULT_LICENSES_PATH
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except yaml.YAMLError:
        return []
    entries = data.get("models", [])
    result = []
    for entry in entries:
        try:
            result.append(
                ModelLicense(
                    id=entry["id"],
                    name=entry["name"],
                    stage=entry["stage"],
                    licence=entry["licence"],
                    commercial=entry["commercial"],
                    source=entry.get("source", ""),
                    note=entry.get("note", ""),
                    match=entry.get("match") or {},
                )
            )
        except KeyError:
            continue  # malformed entry, skip rather than crash doctor
    return result


def _get_dotted(cfg_dict: dict, dotted_path: str) -> Any:
    node: Any = cfg_dict
    for part in dotted_path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def active_models_for_config(cfg_dict: dict, licenses: list[ModelLicense]) -> list[ModelLicense]:
    """Return every ModelLicense entry whose `match` conditions all hold
    against the given config (as a plain dict, e.g. `cfg.model_dump()`)."""
    active = []
    for entry in licenses:
        if all(_get_dotted(cfg_dict, key) == value for key, value in entry.match.items()):
            active.append(entry)
    return active


def non_commercial_active_models(cfg_dict: dict, licenses: list[ModelLicense]) -> list[ModelLicense]:
    """Active models whose licence is not confirmed commercial-safe
    (commercial is False or "check")."""
    return [m for m in active_models_for_config(cfg_dict, licenses) if not m.is_commercial_safe]
