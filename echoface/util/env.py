"""Loads .env (if present) into the process environment, and reads a
small set of environment-variable overrides for machine-specific or
secret-shaped config values (Ollama host, HF token passthrough, XTTS
licence acknowledgement, ffmpeg binary override).

Nothing here is required — every value has the same default it always
had — this just lets deployment-specific values live outside the repo
and outside config/*.yaml (which IS committed), per the project's
security policy (see SECURITY.md and .env.example).
"""

from __future__ import annotations

import os
from pathlib import Path


def load_env(dotenv_path: Path | None = None) -> None:
    """Load a .env file into os.environ (does not override already-set
    env vars). Safe to call multiple times. No-ops quietly if
    python-dotenv isn't installed or no .env file exists — .env is
    optional, config/*.yaml + defaults always work standalone."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    path = dotenv_path or Path.cwd() / ".env"
    if path.exists():
        load_dotenv(dotenv_path=path, override=False)


def env_override(name: str, default: str | None) -> str | None:
    """Return os.environ[name] if set, else default. Thin wrapper kept as
    a single choke point so it's easy to see every env var echoface reads
    (grep for env_override)."""
    return os.environ.get(name, default)
