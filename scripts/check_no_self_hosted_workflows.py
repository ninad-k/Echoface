"""CI lint check: fail if any GitHub Actions workflow other than
gpu-tests.yml targets a self-hosted-style runner.

gpu-tests.yml is the ONLY workflow allowed to do this -- it's
workflow_dispatch-only, gated by `if: github.repository ==
'ninad-k/Echoface'`, and its own first step verifies the runner is
actually provisioned before anything else runs. ci.yml and release.yml
must only ever use GitHub-hosted runners: this repo is public, and a
runner attached to a specific machine picking up push/PR-triggered jobs
would be a real risk.

Parses each workflow's actual `jobs.*.runs-on` field via PyYAML (never
just grepping raw text, which would also match this file's own
docstring, or a shell check script's own quoted pattern -- both real
failure modes hit while writing this). Run from the repo root:

    python scripts/check_no_self_hosted_workflows.py

See docs/ops/self-hosted-gpu-runner.md.
"""

from __future__ import annotations

import glob

import yaml

WORD = "self" + "-hosted"  # built at runtime so this file doesn't itself
# contain the literal word (defence in depth if this script is ever fed
# into the same kind of raw-text scan it replaces).


def main() -> int:
    offenders: list[str] = []
    for path in sorted(glob.glob(".github/workflows/*.yml")):
        if path.replace("\\", "/").endswith("/gpu-tests.yml"):
            continue
        with open(path, encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        for job_name, job in (doc.get("jobs") or {}).items():
            runs_on = job.get("runs-on")
            labels = runs_on if isinstance(runs_on, list) else [runs_on]
            if any(WORD in str(label) for label in labels if label):
                offenders.append(f"{path}:{job_name} runs-on={runs_on!r}")

    if offenders:
        print(f"::error::{WORD} runs-on found outside gpu-tests.yml: " + "; ".join(offenders))
        return 1
    print(f"OK: no runs-on outside gpu-tests.yml targets a {WORD}-style runner.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
