<#
.SYNOPSIS
  One-time Windows setup for Echoface: creates the three venvs (orchestrator,
  envs\face, envs\tts) on Python 3.14, installs dependencies (including a
  CUDA 12.8 torch build for Blackwell/RTX 50-series GPUs), patches basicsr
  for modern Python/torchvision, and verifies CUDA in envs\face.

.NOTES
  Run from the repo root: powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
  Idempotent: safe to re-run; existing venvs/files are left alone unless
  -Force is passed for that step.

  Does NOT download model checkpoints or clone vendor repos other than what
  is listed below under "vendor repos" - those are cloned here because our
  own runner scripts (scripts\wav2lip_runner.py, scripts\gfpgan_runner.py)
  import their (patched) architecture/detector code directly. Model WEIGHTS
  are a separate, explicit step (large, individually licensed) - see
  models\MODELS.md for exact source URLs/checksums/licences already
  recorded from this machine's provisioning run.
#>

param(
    [string]$PythonExe = "py -3.14",
    [string]$CudaIndexUrl = "https://download.pytorch.org/whl/cu128",
    [switch]$SkipFace,
    [switch]$SkipTts,
    [switch]$SkipVendorClone
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition | Split-Path -Parent

Write-Host "== Echoface Windows setup (Python 3.14, CUDA 12.8) ==" -ForegroundColor Cyan
Set-Location $root

$pyParts = $PythonExe -split " "
$pyExe = $pyParts[0]
$pyArgs = $pyParts[1..($pyParts.Length - 1)]

function New-Venv([string]$Path) {
    if (Test-Path "$Path\Scripts\python.exe") {
        Write-Host "Venv already exists: $Path" -ForegroundColor Yellow
        return
    }
    Write-Host "Creating venv: $Path" -ForegroundColor Green
    & $pyExe @pyArgs -m venv $Path
}

# ---------------------------------------------------------------------
# 1. Orchestrator venv (.venv) - Python 3.14, no torch.
# ---------------------------------------------------------------------
New-Venv ".venv"
Write-Host "Installing orchestrator package (editable) + dev/captions extras..." -ForegroundColor Green
& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\pip.exe" install -e ".[dev,captions]"

# ---------------------------------------------------------------------
# 2. Vendor repos (Wav2Lip / SadTalker / GFPGAN) - cloned so our runner
#    scripts can import their (patched) model/detector code directly.
# ---------------------------------------------------------------------
if (-not $SkipVendorClone) {
    if (-not (Test-Path "vendor")) { New-Item -ItemType Directory -Path "vendor" | Out-Null }
    $repos = @{
        "Wav2Lip"  = "https://github.com/Rudrabha/Wav2Lip.git"
        "SadTalker" = "https://github.com/OpenTalker/SadTalker.git"
        "GFPGAN"   = "https://github.com/TencentARC/GFPGAN.git"
        "CodeFormer" = "https://github.com/sczhou/CodeFormer.git"
    }
    foreach ($name in $repos.Keys) {
        $dest = "vendor\$name"
        if (Test-Path $dest) {
            Write-Host "vendor\$name already cloned, skipping" -ForegroundColor Yellow
        } else {
            Write-Host "Cloning $name..." -ForegroundColor Green
            git clone --depth 1 $repos[$name] $dest
        }
    }
    # Wav2Lip's audio.py needs one keyword-arg fix for modern librosa
    # (librosa.filters.mel is keyword-only for sr/n_fft since ~0.10).
    # See vendor\patches\wav2lip_audio_librosa_kwargs.patch for the diff.
    $audioPy = "vendor\Wav2Lip\audio.py"
    if ((Test-Path $audioPy) -and (Select-String -Path $audioPy -Pattern "librosa.filters.mel\(hp.sample_rate, hp.n_fft" -Quiet)) {
        Write-Host "Patching vendor\Wav2Lip\audio.py for modern librosa..." -ForegroundColor Green
        (Get-Content $audioPy -Raw) -replace `
            [regex]::Escape("librosa.filters.mel(hp.sample_rate, hp.n_fft, n_mels=hp.num_mels,"), `
            "librosa.filters.mel(sr=hp.sample_rate, n_fft=hp.n_fft, n_mels=hp.num_mels," | `
            Set-Content -NoNewline $audioPy
    }
    # Wav2Lip's own face-detection checkpoint (S3FD), needed by
    # scripts\wav2lip_runner.py regardless of which face weights are used.
    $s3fd = "vendor\Wav2Lip\face_detection\detection\sfd\s3fd.pth"
    if (-not (Test-Path $s3fd)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $s3fd) | Out-Null
        Write-Host "Downloading S3FD face-detection weights..." -ForegroundColor Green
        Invoke-WebRequest -Uri "https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth" -OutFile $s3fd
    }

    # SadTalker needs three small NumPy-2.x compatibility fixes to run at
    # all (float(ndarray)/ragged-array patterns NumPy 1.x silently
    # coerced). Idempotent - see vendor\patches\sadtalker_numpy2_compat.patch
    # for the full diff/rationale.
    if (Test-Path "vendor\SadTalker") {
        Write-Host "Patching vendor\SadTalker for NumPy 2.x compatibility..." -ForegroundColor Green
        & ".venv\Scripts\python.exe" "vendor\patches\patch_sadtalker.py" "vendor\SadTalker"
    }

    # CodeFormer bundles its own local basicsr/facelib copies (not pip
    # installed) but never generates basicsr/version.py outside a real
    # `pip install`. See vendor\patches\patch_codeformer.py.
    if (Test-Path "vendor\CodeFormer") {
        Write-Host "Patching vendor\CodeFormer (basicsr/version.py)..." -ForegroundColor Green
        & ".venv\Scripts\python.exe" "vendor\patches\patch_codeformer.py" "vendor\CodeFormer"
    }

    # CodeFormer's own facelib detector/parser weights are the same files
    # GFPGAN's facexlib already needs (models\gfpgan\*.pth) - reuse them
    # instead of a second download, once both are present.
    $cfFacelib = "vendor\CodeFormer\weights\facelib"
    if ((Test-Path "models\gfpgan\detection_Resnet50_Final.pth") -and (-not (Test-Path "$cfFacelib\detection_Resnet50_Final.pth"))) {
        New-Item -ItemType Directory -Force -Path $cfFacelib | Out-Null
        Copy-Item "models\gfpgan\detection_Resnet50_Final.pth" "$cfFacelib\detection_Resnet50_Final.pth"
        Copy-Item "models\gfpgan\parsing_parsenet.pth" "$cfFacelib\parsing_parsenet.pth"
        Write-Host "Copied shared facelib weights into vendor\CodeFormer\weights\facelib" -ForegroundColor Green
    }
    $cfWeights = "vendor\CodeFormer\weights\CodeFormer"
    if ((Test-Path "models\codeformer\codeformer.pth") -and (-not (Test-Path "$cfWeights\codeformer.pth"))) {
        New-Item -ItemType Directory -Force -Path $cfWeights | Out-Null
        Copy-Item "models\codeformer\codeformer.pth" "$cfWeights\codeformer.pth"
    }

    # The "realtest" sample presenter's portrait is SadTalker's own demo
    # asset - not committed to this repo (see assets\ATTRIBUTION.md for
    # why), copied locally here instead.
    $realtestSrc = "vendor\SadTalker\examples\source_image\art_10.png"
    $realtestDst = "assets\portraits\realtest\portrait.png"
    if ((Test-Path $realtestSrc) -and (-not (Test-Path $realtestDst))) {
        New-Item -ItemType Directory -Force -Path (Split-Path $realtestDst) | Out-Null
        Copy-Item $realtestSrc $realtestDst
        Write-Host "Copied realtest presenter portrait from vendor\SadTalker\examples" -ForegroundColor Green
    }
} else {
    Write-Host "Skipping vendor repo clone (-SkipVendorClone)" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------
# 3. Face venv (Wav2Lip / SadTalker / GFPGAN) - Python 3.14, torch cu128.
# ---------------------------------------------------------------------
if (-not $SkipFace) {
    New-Venv "envs\face"
    Write-Host "Installing torch (CUDA 12.8, Blackwell/sm_120-capable) into envs\face..." -ForegroundColor Green
    & "envs\face\Scripts\pip.exe" install torch torchvision torchaudio --index-url $CudaIndexUrl
    if (Test-Path "requirements-face.txt") {
        Write-Host "Installing face-stage requirements..." -ForegroundColor Green
        & "envs\face\Scripts\pip.exe" install -r requirements-face.txt
    }

    # basicsr (a GFPGAN dependency) is unmaintained and fails to build on
    # Python 3.13+ / modern torchvision; patch its sdist before installing.
    # See vendor\patches\patch_basicsr.py for exactly what and why.
    $basicsrInstalled = & "envs\face\Scripts\python.exe" -c "import basicsr" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Downloading + patching basicsr==1.4.2..." -ForegroundColor Green
        $tmpDir = Join-Path $env:TEMP "echoface_basicsr_build"
        Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Path $tmpDir | Out-Null
        $sdistUrl = "https://files.pythonhosted.org/packages/86/41/00a6b000f222f0fa4c6d9e1d6dcc9811a374cabb8abb9d408b77de39648c/basicsr-1.4.2.tar.gz"
        $tarPath = Join-Path $tmpDir "basicsr.tar.gz"
        Invoke-WebRequest -Uri $sdistUrl -OutFile $tarPath
        tar -xzf $tarPath -C $tmpDir
        & "envs\face\Scripts\python.exe" "vendor\patches\patch_basicsr.py" (Join-Path $tmpDir "basicsr-1.4.2")
        & "envs\face\Scripts\pip.exe" install (Join-Path $tmpDir "basicsr-1.4.2")
    } else {
        Write-Host "basicsr already installed in envs\face" -ForegroundColor Yellow
    }
    & "envs\face\Scripts\pip.exe" install gfpgan --no-deps
    & "envs\face\Scripts\pip.exe" install gdown  # for fetching the official Wav2Lip Google Drive weights
    & "envs\face\Scripts\pip.exe" install lpips  # CodeFormer arch import-time dependency

    # scripts\gfpgan_runner.py / codeformer_runner.py import
    # echoface.util.restore_blend (pure-numpy region mask/blend, no
    # torch/cv2) for --region mouth - install the orchestrator package
    # (no deps, already satisfied by requirements-face.txt) into envs\face
    # too so that import resolves.
    & "envs\face\Scripts\pip.exe" install -e . --no-deps -q

    Write-Host "Verifying CUDA in envs\face (real tensor op)..." -ForegroundColor Green
    & "envs\face\Scripts\python.exe" -c "import torch; print('torch', torch.__version__); print('cuda available:', torch.cuda.is_available()); print('device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'n/a'); a=torch.randn(512,512,device='cuda' if torch.cuda.is_available() else 'cpu'); print('matmul ok, sum=', (a@a).sum().item())"
} else {
    Write-Host "Skipping envs\face (-SkipFace)" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------
# 4. TTS venv (Piper / XTTS) - Python 3.14.
# ---------------------------------------------------------------------
if (-not $SkipTts) {
    New-Venv "envs\tts"
    Write-Host "Installing torch (CUDA 12.8) into envs\tts (needed for the optional XTTS engine)..." -ForegroundColor Green
    & "envs\tts\Scripts\pip.exe" install torch torchaudio --index-url $CudaIndexUrl
    if (Test-Path "requirements-tts.txt") {
        Write-Host "Installing tts-stage requirements..." -ForegroundColor Green
        & "envs\tts\Scripts\pip.exe" install -r requirements-tts.txt
    }
} else {
    Write-Host "Skipping envs\tts (-SkipTts)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "== Next steps ==" -ForegroundColor Cyan
Write-Host "1. Download model weights (see models\MODELS.md for the exact official"
Write-Host "   URLs, versions, SHA256 and licences already used on this machine):"
Write-Host "     - models\wav2lip\wav2lip_gan.pth        (Wav2Lip README -> Google Drive)"
Write-Host "     - models\gfpgan\GFPGANv1.4.pth           (GFPGAN GitHub release)
     - models\codeformer\codeformer.pth       (CodeFormer GitHub release, optional restore engine, S-Lab non-commercial licence)"
Write-Host "     - models\piper\en_US-lessac-medium.onnx(.json) (rhasspy/piper-voices on HF)"
Write-Host "     - vendor\SadTalker\checkpoints\*         (SadTalker README -> GitHub release, optional)"
Write-Host "2. Add a real portrait/idle asset + signed consent under consent\, and"
Write-Host "   update assets\portraits\<name>\meta.yaml's consent_ref."
Write-Host "3. Start Ollama (ollama serve) and pull a model: ollama pull qwen2.5:7b"
Write-Host "4. Run: .venv\Scripts\echoface doctor"
