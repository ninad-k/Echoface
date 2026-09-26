<#
.SYNOPSIS
    Manage a self-hosted GitHub Actions runner for Echoface's on-demand
    GPU test workflow (.github/workflows/gpu-tests.yml).

.DESCRIPTION
    See docs/ops/self-hosted-gpu-runner.md for the full guide (security
    model, why on-demand, step-by-step setup, triggering a run, reading
    results, and removal). This script only automates the mechanical
    steps; it never registers or starts anything on its own -- every
    subcommand with a real side effect (register, start, remove) is
    something YOU run explicitly, when you intend that side effect.

    Subcommands:
      install   Download the latest official actions/runner win-x64
                release, verify its SHA256 against the value GitHub
                publishes in the release notes, extract it to
                -RunnerDir (outside this repo), and write the runner's
                own .env file with ECHOFACE_HOME=<RepoPath> (loaded
                automatically into every job this runner executes).
      register  Fetch a short-lived registration token via
                `gh api -X POST` at the moment you run this -- never
                printed, logged, or written to disk -- then run
                config.cmd --unattended (no --runasservice: this is an
                on-demand runner, started manually with `start` and
                stopped with Ctrl+C).
      start     Run run.cmd in the foreground. Ctrl+C stops it. Only
                listens for jobs while this is running.
      status    Report whether the runner is installed/configured and
                point at its own logs -- read-only, no GitHub API call.
      remove    Fetch a short-lived removal token the same way as
                register, then run config.cmd remove.

.PARAMETER Command
    One of: install, register, start, status, remove.

.PARAMETER RunnerDir
    Where the runner is installed. Default: a folder under your user
    profile, deliberately OUTSIDE this repo checkout (the runner tool
    itself is not Echoface code and has no reason to be versioned or
    to live inside a directory Actions will check code out into).

.PARAMETER RepoPath
    Path to the provisioned Echoface install (envs\, models\, vendor\
    already set up) -- becomes ECHOFACE_HOME for every job. Default:
    this script's own repo checkout.

.PARAMETER GitHubRepo
    The "<owner>/<repo>" this runner registers against. Default:
    ninad-k/Echoface.

.PARAMETER WhatIf
    Dry run: print exactly what each subcommand would do -- URLs,
    hashes, file paths, the config.cmd/run.cmd command line it would
    invoke -- without downloading, extracting, writing files, fetching
    a token, or running anything. register/start/remove are ALWAYS
    safe to explore this way first.

.EXAMPLE
    scripts\gpu_runner.ps1 install
    scripts\gpu_runner.ps1 register -WhatIf
    scripts\gpu_runner.ps1 register
    scripts\gpu_runner.ps1 start
    scripts\gpu_runner.ps1 status
    scripts\gpu_runner.ps1 remove -WhatIf
#>

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("install", "register", "start", "status", "remove")]
    [string]$Command,

    [string]$RunnerDir = (Join-Path $env:USERPROFILE "actions-runner-echoface"),

    [string]$RepoPath = $(
        # $PSScriptRoot is usually populated when a script runs via
        # -File, but not always (e.g. some wrappers/dot-sourcing
        # contexts) -- fall back to $MyInvocation before giving up, so
        # a caller isn't forced to pass -RepoPath just to work around
        # an empty default in edge cases.
        $root = $PSScriptRoot
        if ([string]::IsNullOrEmpty($root) -and $MyInvocation.MyCommand.Path) {
            $root = Split-Path -Parent $MyInvocation.MyCommand.Path
        }
        if ([string]::IsNullOrEmpty($root)) {
            throw "Could not determine this script's own directory to default -RepoPath from. Pass -RepoPath <path-to-provisioned-Echoface-repo> explicitly."
        }
        (Resolve-Path (Join-Path $root "..")).Path
    ),

    [string]$GitHubRepo = "ninad-k/Echoface",

    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$RunnerLabel = "gpu"
$RunnerName = "$($env:COMPUTERNAME)-gpu"

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-DryRun {
    param([string]$Message)
    Write-Host "[WhatIf] $Message" -ForegroundColor Yellow
}

function Get-LatestWindowsRunnerAsset {
    <# Returns @{ Version=...; Url=...; FileName=...; Sha256=... } for the
       latest official win-x64 actions/runner release, parsed from
       GitHub's own release API + release-notes SHA-256 checksums
       section -- never a third-party mirror. #>
    Write-Step "Querying latest actions/runner release via GitHub API..."
    $releaseJson = gh api repos/actions/runner/releases/latest
    if ($LASTEXITCODE -ne 0) {
        throw "gh api repos/actions/runner/releases/latest failed (exit $LASTEXITCODE) -- is `gh` authenticated? Run `gh auth status`."
    }
    $release = $releaseJson | ConvertFrom-Json

    $asset = $release.assets | Where-Object { $_.name -match '^actions-runner-win-x64-[\d\.]+\.zip$' } | Select-Object -First 1
    if (-not $asset) {
        throw "No win-x64 asset found in release $($release.tag_name) -- release asset naming may have changed; check https://github.com/actions/runner/releases/latest manually."
    }

    # GitHub's release body embeds each asset's SHA-256 between HTML
    # comment markers, e.g.:
    #   - actions-runner-win-x64-2.337.0.zip <!-- BEGIN SHA win-x64 -->1150...cfc<!-- END SHA win-x64 -->
    $shaMatch = [regex]::Match($release.body, '<!-- BEGIN SHA win-x64 -->([0-9a-fA-F]{64})<!-- END SHA win-x64 -->')
    if (-not $shaMatch.Success) {
        throw "Could not find a win-x64 SHA-256 checksum in release $($release.tag_name)'s notes -- GitHub's release-notes format may have changed. Refusing to install without a verifiable checksum; check https://github.com/actions/runner/releases/latest manually."
    }

    return @{
        Version  = $release.tag_name
        Url      = $asset.browser_download_url
        FileName = $asset.name
        Sha256   = $shaMatch.Groups[1].Value.ToLowerInvariant()
    }
}

function Install-Runner {
    $info = Get-LatestWindowsRunnerAsset
    Write-Host "Latest release: $($info.Version)"
    Write-Host "Asset:          $($info.FileName)"
    Write-Host "Expected SHA256: $($info.Sha256)"

    if ($WhatIf) {
        Write-DryRun "Would download $($info.Url)"
        Write-DryRun "Would verify SHA256 against $($info.Sha256)"
        Write-DryRun "Would extract to $RunnerDir"
        Write-DryRun "Would write $RunnerDir\.env with ECHOFACE_HOME=$RepoPath"
        return
    }

    if (-not (Test-Path $RunnerDir)) {
        New-Item -ItemType Directory -Path $RunnerDir -Force | Out-Null
    }

    $zipPath = Join-Path $RunnerDir $info.FileName
    Write-Step "Downloading $($info.Url) -> $zipPath"
    Invoke-WebRequest -Uri $info.Url -OutFile $zipPath

    Write-Step "Verifying SHA256..."
    $actualHash = (Get-FileHash -Path $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $info.Sha256) {
        Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
        throw "SHA256 mismatch for $($info.FileName): expected $($info.Sha256), got $actualHash. Deleted the downloaded file. Do NOT proceed -- this could mean a corrupted download or a compromised mirror."
    }
    Write-Host "SHA256 verified: $actualHash" -ForegroundColor Green

    Write-Step "Extracting to $RunnerDir..."
    Expand-Archive -Path $zipPath -DestinationPath $RunnerDir -Force
    Remove-Item $zipPath -Force

    $envPath = Join-Path $RunnerDir ".env"
    Write-Step "Writing $envPath (ECHOFACE_HOME=$RepoPath)..."
    "ECHOFACE_HOME=$RepoPath" | Out-File -FilePath $envPath -Encoding utf8 -NoNewline
    Write-Host ""
    Write-Host "Installed. Next: scripts\gpu_runner.ps1 register" -ForegroundColor Green
}

function Get-ShortLivedToken {
    param(
        [ValidateSet("registration-token", "remove-token")]
        [string]$Kind
    )
    # Fetched fresh every call, held only in a local variable, never
    # written to disk or printed -- these tokens expire in ~1 hour and
    # are single-purpose (config.cmd consumes them immediately).
    $json = gh api -X POST "repos/$GitHubRepo/actions/runners/$Kind"
    if ($LASTEXITCODE -ne 0) {
        throw "gh api -X POST repos/$GitHubRepo/actions/runners/$Kind failed (exit $LASTEXITCODE) -- confirm `gh auth status` shows an account with admin access to $GitHubRepo."
    }
    return ($json | ConvertFrom-Json).token
}

function Register-Runner {
    $configCmd = Join-Path $RunnerDir "config.cmd"
    if (-not $WhatIf -and -not (Test-Path $configCmd)) {
        throw "$configCmd not found -- run 'scripts\gpu_runner.ps1 install' first."
    }

    if ($WhatIf) {
        Write-DryRun "Would fetch a short-lived registration token via: gh api -X POST repos/$GitHubRepo/actions/runners/registration-token"
        Write-DryRun "Would then run (token redacted below; the real command never logs it):"
        Write-DryRun "  $configCmd --unattended --url https://github.com/$GitHubRepo --token <redacted> --name $RunnerName --labels $RunnerLabel --work _work --replace"
        return
    }

    $token = Get-ShortLivedToken -Kind "registration-token"
    Write-Step "Registering as '$RunnerName' with label '$RunnerLabel'..."
    Push-Location $RunnerDir
    try {
        & $configCmd --unattended --url "https://github.com/$GitHubRepo" --token $token --name $RunnerName --labels $RunnerLabel --work "_work" --replace
    } finally {
        Pop-Location
        Remove-Variable token -ErrorAction SilentlyContinue
    }
    Write-Host ""
    Write-Host "Registered. Next: scripts\gpu_runner.ps1 start (run it, then trigger a workflow run from another terminal/machine)." -ForegroundColor Green
}

function Start-Runner {
    $runCmd = Join-Path $RunnerDir "run.cmd"
    if ($WhatIf) {
        Write-DryRun "Would run $runCmd in the foreground (blocks this terminal; Ctrl+C stops it and the runner goes offline)."
        return
    }
    if (-not (Test-Path $runCmd)) {
        throw "$runCmd not found -- run 'scripts\gpu_runner.ps1 install' and 'register' first."
    }
    Write-Step "Starting runner in the foreground -- Ctrl+C to stop. It only accepts jobs while this is running."
    Push-Location $RunnerDir
    try {
        & $runCmd
    } finally {
        Pop-Location
    }
}

function Get-RunnerStatus {
    Write-Host "Runner directory: $RunnerDir"
    if (-not (Test-Path $RunnerDir)) {
        Write-Host "Status: NOT INSTALLED (directory does not exist)" -ForegroundColor Yellow
        return
    }
    $configCmd = Join-Path $RunnerDir "config.cmd"
    if (-not (Test-Path $configCmd)) {
        Write-Host "Status: directory exists but does not look like an extracted runner (no config.cmd)" -ForegroundColor Yellow
        return
    }
    $runnerFile = Join-Path $RunnerDir ".runner"
    $registered = Test-Path $runnerFile
    Write-Host "Installed: yes"
    Write-Host "Registered: $(if ($registered) { 'yes' } else { 'no -- run: scripts\gpu_runner.ps1 register' })"

    $envFile = Join-Path $RunnerDir ".env"
    if (Test-Path $envFile) {
        Write-Host "Runner .env:"
        Get-Content $envFile | ForEach-Object { Write-Host "  $_" }
    } else {
        Write-Host ".env: missing (ECHOFACE_HOME won't be set for jobs -- re-run 'install')" -ForegroundColor Yellow
    }

    $listener = Get-Process -Name "Runner.Listener" -ErrorAction SilentlyContinue
    Write-Host "Currently listening: $(if ($listener) { 'yes (Runner.Listener.exe running)' } else { 'no -- run: scripts\gpu_runner.ps1 start' })"

    $logDir = Join-Path $RunnerDir "_diag"
    if (Test-Path $logDir) {
        Write-Host "Logs: $logDir"
    }
}

function Remove-Runner {
    $configCmd = Join-Path $RunnerDir "config.cmd"
    if ($WhatIf) {
        Write-DryRun "Would fetch a short-lived removal token via: gh api -X POST repos/$GitHubRepo/actions/runners/remove-token"
        Write-DryRun "Would then run (token redacted below): $configCmd remove --token <redacted>"
        return
    }
    if (-not (Test-Path $configCmd)) {
        throw "$configCmd not found -- nothing to remove at $RunnerDir."
    }
    $token = Get-ShortLivedToken -Kind "remove-token"
    Write-Step "Removing runner registration..."
    Push-Location $RunnerDir
    try {
        & $configCmd remove --token $token
    } finally {
        Pop-Location
        Remove-Variable token -ErrorAction SilentlyContinue
    }
    Write-Host "Removed from GitHub. The $RunnerDir folder itself was left in place; delete it manually if you want it fully gone." -ForegroundColor Green
}

switch ($Command) {
    "install" { Install-Runner }
    "register" { Register-Runner }
    "start" { Start-Runner }
    "status" { Get-RunnerStatus }
    "remove" { Remove-Runner }
}
