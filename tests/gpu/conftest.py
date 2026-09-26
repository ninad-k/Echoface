"""tests/gpu-local pytest configuration: turns every prerequisite-missing
skip in this directory into a hard failure when `ECHOFACE_REQUIRE_GPU_TESTS`
is set to a truthy value.

Every test in `tests/gpu/test_real_engines.py` self-skips (via
`pytest.skip(...)`, either directly or through the shared `_require()`
helper) rather than failing when its prerequisite -- a provisioned venv,
downloaded model weights, a real presenter asset, a reachable Ollama --
isn't present. That's the right default for a partially-provisioned dev
machine (still get useful signal from the tests that *can* run), but it
means a machine that's supposed to be fully provisioned -- the self-hosted
GPU CI runner, specifically -- could report an all-green run that actually
exercised nothing at all, which is worse than useless: it looks like a
passing signal while proving nothing.

`gpu-tests.yml` sets `ECHOFACE_REQUIRE_GPU_TESTS=1` for exactly this
reason. Locally, leave it unset (the default) unless you specifically want
this same strictness.
"""

from __future__ import annotations

import os

import pytest

_TRUTHY = {"1", "true", "yes", "on"}


def _require_gpu_tests_enabled() -> bool:
    return os.environ.get("ECHOFACE_REQUIRE_GPU_TESTS", "").strip().lower() in _TRUTHY


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """Rewrite a 'skipped' outcome to 'failed' for the *call* phase only
    (not collection-time skips like the module-level ffmpeg-availability
    `pytestmark`, and not setup/teardown skips from unrelated fixtures)
    when the strict env var is set. Implemented as a hookwrapper around
    report construction rather than touching every test/`_require()`
    call site individually, so a new gpu test added later gets this for
    free automatically."""
    outcome = yield
    if call.when != "call" or not _require_gpu_tests_enabled():
        return
    report = outcome.get_result()
    if report.skipped:
        original = report.longrepr
        report.outcome = "failed"
        report.longrepr = (
            f"{item.nodeid}: prerequisite-missing skip treated as a failure "
            "because ECHOFACE_REQUIRE_GPU_TESTS is set -- this machine is "
            "expected to be fully provisioned (see "
            f"docs/ops/self-hosted-gpu-runner.md).\nOriginal skip: {original}"
        )
