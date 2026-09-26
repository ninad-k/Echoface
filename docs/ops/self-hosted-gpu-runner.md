# Self-hosted GPU runner (for real-engine CI tests)

`tests/gpu/` exercises real Wav2Lip/GFPGAN/CodeFormer/Piper/XTTS/Ollama
inference on tiny inputs — real signal that the actual model code paths
still work after a dependency bump, not just that the orchestrator's
plumbing is sound (that's what `ci.yml`'s GitHub-hosted, dummy-engine
tests already cover). Those real engines need a GPU and gigabytes of
venvs/model weights that only exist on a provisioned machine — they can
never run on GitHub's own hosted runners.

`.github/workflows/gpu-tests.yml` runs them, but **only** when someone
manually triggers it (`workflow_dispatch`) against a **self-hosted**
runner you register and start yourself, on demand. This doc covers the
security model, setup, day-to-day use, and removal.

## Security model — read this first

**The repo is public.** A self-hosted runner is a real machine (this
one) that executes whatever a triggered workflow run tells it to. That
is a meaningfully different risk than GitHub's own hosted, ephemeral
runners, so several things are deliberately layered together here:

1. **Fork PR approval is already set to require approval for all
   outside contributors** (repo setting: Actions → General → Fork pull
   request workflows → *Require approval for all outside
   collaborators*). This means a stranger opening a PR from a fork
   cannot get *any* workflow to run — including this one — without a
   maintainer explicitly clicking "Approve and run" first. This repo
   setting is already configured; this doc doesn't change it and
   nothing here should ever need to.
2. **`gpu-tests.yml` is `workflow_dispatch`-only.** It never triggers on
   `push` or `pull_request`. Nothing — not even an approved fork PR —
   can make it run automatically; only a maintainer running `gh workflow
   run gpu-tests.yml` (or clicking "Run workflow" in the Actions tab)
   triggers it, and only with `workflow_dispatch`'s inputs, not a PR's
   arbitrary head SHA content controlling what step commands execute.
3. **`if: github.repository == 'ninad-k/Echoface'`** on the job itself,
   defence in depth against ever being invoked as a reusable workflow
   from a fork.
4. **`ci.yml` and `release.yml` can never target this runner.** A CI
   lint step (`scripts/check_no_self_hosted_workflows.py`, run in
   `ci.yml`'s `lint` job) fails the build if any workflow file other
   than `gpu-tests.yml` ever sets `runs-on` to something self-hosted —
   this is the thing that would actually matter if it broke silently,
   since those two DO trigger on every push/PR.
5. **The runner is on-demand, not a service.** `scripts/gpu_runner.ps1
   start` runs it in the foreground; it only accepts jobs while that
   terminal is open, and stops the instant you Ctrl+C it or close the
   terminal. There is no Windows service, no auto-start, no
   always-listening daemon — deliberately, so it isn't sitting there
   accepting jobs when you're not actively testing something. **Stop it
   (Ctrl+C) as soon as your test run finishes.**
6. **The runner process runs as your own Windows user account** — the
   same account you're using to read this doc, with the same file
   permissions, the same access to your other files, and the same
   network access. It is not sandboxed or isolated from the rest of
   this machine. Only trigger `gpu-tests.yml` runs against commits/code
   you already trust (your own pushes to `main`, or a PR you've read).
7. **Registration/removal tokens are never written to disk or logged.**
   `scripts/gpu_runner.ps1 register`/`remove` fetch a short-lived
   (~1 hour, single-use) token via `gh api -X POST` at the moment you
   run the command, hold it only in a local PowerShell variable, pass
   it straight to `config.cmd`, and explicitly clear the variable
   afterward. Nothing in this repo ever needs a long-lived Personal
   Access Token for runner management — `gh`'s own existing
   authentication (`gh auth login`) is enough.

If any of that doesn't sound like an acceptable trade-off for your
situation, don't register a runner — `gpu-tests.yml` simply stays queued
forever with no self-hosted runner available, and `ci.yml`/`release.yml`
are completely unaffected either way.

## Prerequisites

- This machine, with `envs\face`/`envs\tts` fully provisioned
  (`scripts\setup_windows.ps1`) and model weights downloaded
  (`models\MODELS.md`) — i.e. everything `docs/ops/installation-deployment.md`
  already has you do to run Echoface for real.
- [GitHub CLI](https://cli.github.com/) installed and authenticated
  (`gh auth login`) as an account with admin access to this repo (needed
  only for `register`/`remove`, which fetch short-lived tokens on your
  behalf — see point 7 above).
- PowerShell (the same one everything else in `scripts\` already
  assumes).

## Setup

All commands below are `scripts\gpu_runner.ps1 <subcommand>`, run from a
PowerShell prompt. Every subcommand accepts `-WhatIf` to print exactly
what it would do without doing it — try that first if you want to see
the commands before they run for real. Full parameter docs:
`Get-Help scripts\gpu_runner.ps1 -Full`.

### 1. Install the runner binary

```powershell
scripts\gpu_runner.ps1 install
```

Downloads the latest official `actions/runner` Windows x64 release
directly from `github.com/actions/runner/releases`, verifies its SHA256
against the checksum GitHub publishes in that release's own notes
(refuses to proceed on any mismatch), extracts it to
`$env:USERPROFILE\actions-runner-echoface` (override with `-RunnerDir`,
kept **outside** this repo checkout on purpose — it's a separate tool,
not Echoface code), and writes that folder's `.env` file with
`ECHOFACE_HOME=<this repo's path>` (override with `-RepoPath`). The
Actions runner loads a `.env` file next to `run.cmd` automatically into
every job's environment — this is how `gpu-tests.yml`'s ephemeral
checkout finds `envs\`/`models\`/`vendor\` without them needing to exist
in that checkout (see `echoface/util/proc.py`'s `resolve_asset()`).

### 2. Register it with this repo

```powershell
scripts\gpu_runner.ps1 register
```

Fetches a short-lived registration token (see point 7 above) and runs
`config.cmd --unattended` with label `gpu` and name
`<this-machine>-gpu`. No `--runasservice` — this is intentional (see
point 5 above).

### 3. Start it (on demand, whenever you want to test)

```powershell
scripts\gpu_runner.ps1 start
```

Runs in the foreground. **Ctrl+C to stop it** — do this as soon as
you're done with a test run.

## Triggering a run

With the runner listening (step 3 above, in its own terminal), from
anywhere with `gh` configured:

```powershell
gh workflow run gpu-tests.yml
# or with a narrower marker expression:
gh workflow run gpu-tests.yml -f marker_expr="gpu"
```

## Reading results

```powershell
gh run watch                     # follow the run that was just triggered
gh run list --workflow gpu-tests.yml --limit 5
```

The job's first step verifies `ECHOFACE_HOME` is actually set and
provisioned (`envs\face\python.exe` and a non-empty `models\` present)
and fails immediately with a clear message if not — a "green" run means
the real engines actually ran, not that everything silently skipped
(`ECHOFACE_REQUIRE_GPU_TESTS=1` is set for the job specifically to turn
any prerequisite-missing skip into a hard failure — see
`tests/gpu/conftest.py`). The job also uploads the pytest JUnit XML
(`gpu-test-results.xml`) as a workflow artifact, downloadable from the
run's page or via `gh run download`.

## Stopping / removal

- **Just stop listening for now**: Ctrl+C in the `start` terminal. The
  registration stays valid; run `start` again next time.
- **Fully remove the registration** (e.g. decommissioning this machine,
  or you're done testing for good):
  ```powershell
  scripts\gpu_runner.ps1 remove
  ```
  Fetches a short-lived removal token the same way as `register` and
  runs `config.cmd remove`. The `$RunnerDir` folder itself is left on
  disk afterward (in case you want its logs); delete it manually if you
  want it fully gone.

## Troubleshooting

- **`scripts\gpu_runner.ps1 status`** reports whether the runner is
  installed, registered, and currently listening, without making any
  GitHub API call.
- A queued `gpu-tests.yml` run that never starts almost always means no
  matching `[self-hosted, windows, gpu]` runner is currently online —
  check `status`, then `start` it.
- If the job's first step fails with an `ECHOFACE_HOME` error, check
  `<RunnerDir>\.env` — `scripts\gpu_runner.ps1 install` writes it, but
  it can be edited by hand too if the repo ever moves.

## See also
- `docs/security/threat-model.md` — threat T9 covers this runner
  specifically.
- `docs/qa/test-strategy.md` and `tests/gpu/test_real_engines.py`'s own
  module docstring for what each real-engine test covers.
- `docs/ops/installation-deployment.md` for provisioning `envs\`/
  `models\`/`vendor\` in the first place.
