# First-run setup + launcher. Installs only what is missing, then starts the app.
# Called by start.bat; safe to run every time (second run takes a few seconds).

param([switch]$SetupOnly)  # install everything, don't start the app (setup.bat)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot      # mp-studio\  (app, tools, fonts, input, work, output, assets, learn)
$repo = Split-Path -Parent $root             # repo root  (.claude\ skills and .venv\ live here)
Set-Location $root
# keep the repo root tidy in Explorer: only the start file, mp-studio\ and the read-me files show
# folders only: a hidden FILE cannot be rewritten by tools (Windows denies the overwrite)
".claude", ".claude-plugin", ".venv" | ForEach-Object {
    $p = Join-Path $repo $_; if (Test-Path $p) { (Get-Item $p -Force).Attributes = (Get-Item $p -Force).Attributes -bor [IO.FileAttributes]::Hidden }
}
$port = 8765
$url = "http://127.0.0.1:$port"
$studio = "$url/studio/"
# MP Studio opens as an app window (Edge app mode: no tabs, no address bar); plain browser if Edge is missing
function Open-Studio($u) {
    $edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($edge) { Start-Process $edge "--app=$u --window-size=1280,900" } else { Start-Process $u }
    New-Item -ItemType File -Force (Join-Path $root "work\.studio_window") | Out-Null
}

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
function Need-Winget {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "winget is missing. Install 'App Installer' from the Microsoft Store, then run start.bat again."
    }
}

# Already running? Just open it.
if (-not $SetupOnly) { try { Invoke-WebRequest "$url/api/projects" -UseBasicParsing -TimeoutSec 2 | Out-Null; Open-Studio $studio; exit 0 } catch {} }

# 1. FFmpeg
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "Installing FFmpeg..." -ForegroundColor Cyan
    Need-Winget
    winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
    Refresh-Path
}

# 2. Python 3.12 (faster-whisper has no reliable wheels for 3.13+ yet)
$hasPy312 = $false
try { & py -3.12 -c "import sys" 2>$null; $hasPy312 = ($LASTEXITCODE -eq 0) } catch {}
if (-not $hasPy312) {
    Write-Host "Installing Python 3.12..." -ForegroundColor Cyan
    Need-Winget
    winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
    Refresh-Path
}

# 3. venv + packages (reinstalled only when the requirements files change)
$venv = Join-Path $repo ".venv"
$py = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "Creating Python environment..." -ForegroundColor Cyan
    & py -3.12 -m venv $venv
}
function Stamp-Ok($req, $name) {
    $f = Join-Path $venv $name
    (Test-Path $f) -and ((Get-Content $f -Raw).Trim() -eq (Get-FileHash $req).Hash)
}
# Core packages are small and needed to start: install them now.
if (-not (Stamp-Ok "requirements.txt" ".installed")) {
    Write-Host "Installing Python packages..." -ForegroundColor Cyan
    & $py -m pip install --upgrade pip --quiet
    & $py -m pip install -r requirements.txt
    if ($LASTEXITCODE) { throw "pip install -r requirements.txt failed" }
    # onnxruntime (CPU only, from faster-whisper) and onnxruntime-directml share one module folder:
    # keep only the DirectML build, so the matte can use any GPU (it still runs on the CPU too)
    & $py -m pip uninstall -y onnxruntime --quiet
    & $py -m pip install --force-reinstall --no-deps onnxruntime-directml --quiet
    Set-Content (Join-Path $venv ".installed") (Get-FileHash "requirements.txt").Hash
}

# Remotion skills for Claude (motion graphics). Not redistributed in this repo, so fetched here.
$remotionSkill = Join-Path $repo ".claude\skills\remotion-best-practices"
if (-not (Test-Path $remotionSkill) -and (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Fetching Remotion skills..." -ForegroundColor Cyan
    $tmp = Join-Path $env:TEMP "remotion-skills-$(Get-Random)"
    git clone --depth 1 --quiet https://github.com/remotion-dev/skills $tmp
    if ($LASTEXITCODE -eq 0) { Copy-Item -Recurse (Join-Path $tmp "skills\remotion-best-practices") $remotionSkill }
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}

# HyperFrames skills (HTML/GSAP motion graphics, person cutouts). Fetched the same way; the repo is ~500 MB, so only skills/.
$hfSkills = "hyperframes", "hyperframes-cli", "hyperframes-registry", "media-use"
$hfMissing = @($hfSkills | Where-Object { -not (Test-Path (Join-Path $repo ".claude\skills\$_")) })
if ($hfMissing.Count -and (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Fetching HyperFrames skills..." -ForegroundColor Cyan
    $tmp = Join-Path $env:TEMP "hyperframes-skills-$(Get-Random)"
    git clone --depth 1 --filter=blob:none --sparse --quiet https://github.com/heygen-com/hyperframes $tmp
    if ($LASTEXITCODE -eq 0) { git -C $tmp sparse-checkout set skills }
    if ($LASTEXITCODE -eq 0) {
        $hfMissing | ForEach-Object { Copy-Item -Recurse (Join-Path $tmp "skills\$_") (Join-Path $repo ".claude\skills\$_") }
    }
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}

# Official GSAP skills (greensock/gsap-skills, MIT): correct GSAP timelines, eases and plugins, which HyperFrames runs on
if (-not (Test-Path (Join-Path $repo ".claude\skills\gsap-core")) -and (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Fetching GSAP skills..." -ForegroundColor Cyan
    $tmp = Join-Path $env:TEMP "gsap-skills-$(Get-Random)"
    git clone --depth 1 --quiet https://github.com/greensock/gsap-skills $tmp
    if ($LASTEXITCODE -eq 0) {
        # video-relevant only (react/frameworks/scrolltrigger are for websites and would just cost tokens)
        "gsap-core", "gsap-timeline", "gsap-plugins", "gsap-utils", "gsap-performance" |
            Where-Object { Test-Path (Join-Path $tmp "skills\$_") } |
            ForEach-Object { Copy-Item -Recurse (Join-Path $tmp "skills\$_") (Join-Path $repo ".claude\skills\$_") }
    }
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}

# Big downloads (NVIDIA libs ~1 GB, Whisper model, Node.js for Remotion/HyperFrames) run in a separate window while the app is used.
# Until they finish, transcription falls back to CPU / downloads the model on demand.
$gpu = [bool](Get-Command nvidia-smi -ErrorAction SilentlyContinue)
$needGpu = $gpu -and -not (Stamp-Ok "requirements-gpu.txt" ".installed-gpu")
$needModel = -not (Test-Path (Join-Path $venv ".model-medium"))
# HyperFrames needs Node.js 22+; an older install is upgraded
$needNode = $true
if (Get-Command node -ErrorAction SilentlyContinue) { $needNode = [int]((node --version) -replace '^v(\d+).*', '$1') -lt 22 }
# HyperFrames' hidden headless Chrome (~115 MB): renders without opening (or hanging on) the owner's browser
$needBrowser = -not (Test-Path (Join-Path $env:USERPROFILE ".cache\hyperframes\chrome\chrome-headless-shell"))
if ($needGpu -or $needModel -or $needNode -or $needBrowser) {
    $bg = @()
    if ($needNode) {
        $bg += "Write-Host 'Installing Node.js LTS (for Remotion and HyperFrames motion graphics)...'"
        $bg += "winget install --id OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements"
    }
    if ($needBrowser) {
        $bg += "`$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')"
        $bg += "Write-Host 'Installing the headless browser for motion graphics...'; npx --yes hyperframes browser ensure"
    }
    if ($needGpu) {
        $bg += "Write-Host 'Downloading NVIDIA GPU libraries (~1 GB)...'"
        $bg += "& '$py' -m pip install -r requirements-gpu.txt; if (-not `$LASTEXITCODE) { Set-Content '$venv\.installed-gpu' '$((Get-FileHash "requirements-gpu.txt").Hash)' }"
    }
    if ($needModel) {
        $bg += "Write-Host 'Downloading Whisper medium model (~1.5 GB)...'"
        $bg += "& '$py' -c `"from faster_whisper import download_model; download_model('medium')`"; if (-not `$LASTEXITCODE) { Set-Content '$venv\.model-medium' ok }"
    }
    $bg += "Write-Host 'Background downloads finished. This window closes in 10 s.'; Start-Sleep 10"
    Write-Host "Large downloads continue in a separate minimized window." -ForegroundColor Yellow
    Start-Process powershell -WindowStyle Minimized -WorkingDirectory $root `
        -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ($bg -join "; ")
}

# 4. Working folders (not in git)
"input", "work", "output", "assets\logo", "assets\fonts", "assets\music", "fonts", "learn\inbox", "learn\done" | ForEach-Object {
    New-Item -ItemType Directory -Force (Join-Path $root $_) | Out-Null
}

# Persian caption font (Vazirmatn, OFL-1.1); captions fall back to a font without Persian letters otherwise
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
foreach ($w in "Regular", "Bold") {
    $font = Join-Path $root "fonts\Vazirmatn-$w.ttf"
    if (-not (Test-Path $font)) {
        try { Invoke-WebRequest "https://github.com/rastikerdar/vazirmatn/raw/master/fonts/ttf/Vazirmatn-$w.ttf" -OutFile $font -UseBasicParsing }
        catch { Write-Host "Could not download Vazirmatn-$w (captions still work, in a fallback font)" -ForegroundColor Yellow }
    }
}
# Heavy Persian display font for keywords/titles (Lalezar, OFL-1.1, Google Fonts)
$font = Join-Path $root "fonts\Lalezar-Regular.ttf"
if (-not (Test-Path $font)) {
    try {
        Invoke-WebRequest "https://github.com/google/fonts/raw/main/ofl/lalezar/Lalezar-Regular.ttf" -OutFile $font -UseBasicParsing
        Invoke-WebRequest "https://github.com/google/fonts/raw/main/ofl/lalezar/OFL.txt" -OutFile (Join-Path $root "fonts\OFL-Lalezar.txt") -UseBasicParsing
    } catch { Write-Host "Could not download Lalezar (keywords fall back to Vazirmatn)" -ForegroundColor Yellow }
}
# Commercial fonts (Peyda, Kalameh, Abar, Farhang from fontiran.com) are copied into fonts\ by hand.

if ($SetupOnly) {
    Write-Host "`nSetup done. Open Claude Code in this folder, or run start.bat for the app." -ForegroundColor Green
    exit 0
}

# 5. Run
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"
$env:PYTHONUTF8 = "1"
Write-Host "`nVideo Editor running at $url  (close this window to stop)`n" -ForegroundColor Green
Start-Job -ScriptBlock { param($u, $r) Start-Sleep 2
    $edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($edge) { Start-Process $edge "--app=$u --window-size=1280,900" } else { Start-Process $u } } -ArgumentList $studio, $root | Out-Null
& $py -m uvicorn app.server:app --host 127.0.0.1 --port $port
