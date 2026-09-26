<#
.SYNOPSIS
  Runs the real-engine (GPU/Ollama) regression tests in tests\gpu\, which
  pytest excludes by default (see pyproject.toml's `addopts`).

.DESCRIPTION
  These tests need envs\face / envs\tts fully provisioned
  (scripts\setup_windows.ps1), model weights downloaded (models\MODELS.md),
  and either a GPU or patience for CPU fallback, plus a reachable Ollama
  server with the configured model pulled for the `ollama`-marked test.
  Every test self-skips (not fails) if its specific prerequisite is
  missing, so this is safe to run on a partially-provisioned machine.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\run_gpu_tests.ps1
  powershell -ExecutionPolicy Bypass -File scripts\run_gpu_tests.ps1 -MarkerExpr "gpu"
#>

param(
    [string]$MarkerExpr = "gpu or ollama"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition | Split-Path -Parent
Set-Location $root

if (-not (Test-Path ".venv\Scripts\pytest.exe")) {
    Write-Host 'Orchestrator venv (.venv) not found or missing pytest - run:' -ForegroundColor Red
    Write-Host '  py -3.14 -m venv .venv; .venv\Scripts\pip install -e ".[dev,captions]"' -ForegroundColor Yellow
    exit 1
}

Write-Host "== Running real-engine (GPU/Ollama) tests: -m '$MarkerExpr' ==" -ForegroundColor Cyan
Write-Host '(these are excluded from the default test run; see pyproject.toml)' -ForegroundColor DarkGray

& ".venv\Scripts\pytest.exe" -v -m $MarkerExpr tests\gpu --no-header
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host "GPU/Ollama tests: PASS (or skipped where unprovisioned)" -ForegroundColor Green
} else {
    Write-Host "GPU/Ollama tests: FAILURES - see output above" -ForegroundColor Red
}
exit $exitCode
