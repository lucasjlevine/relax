# Start relax (backend + frontend) on Windows.
# Usage (from PowerShell in the repo root):
#   .\start.ps1           # install deps if needed, run locally
#   .\start.ps1 -Docker   # build & run with Docker Compose
#   .\start.ps1 -Setup    # install deps only, do not start servers

[CmdletBinding()]
param(
    [switch]$Docker,
    [switch]$Setup,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Write-Info([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Die([string]$Message) {
    Write-Host "Error: $Message" -ForegroundColor Red
    exit 1
}

if ($Help) {
    @"
Usage: .\start.ps1 [-Docker] [-Setup]

  (default)  Create a Python venv, install backend + frontend deps, start both servers
  -Docker    Run with Docker Compose instead (requires Docker)
  -Setup     Install dependencies only; do not start servers

If script execution is blocked, run once:
  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
"@
    exit 0
}

# --- Docker path -------------------------------------------------------------

if ($Docker) {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Die "Docker is not installed. Install Docker Desktop, then retry."
    }
    docker compose version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Die "Docker Compose is unavailable. Update Docker Desktop and retry."
    }

    Write-Info "Building and starting with Docker Compose…"
    docker compose up --build
    exit $LASTEXITCODE
}

# --- Prerequisite checks -----------------------------------------------------

$script:PythonExe = $null
$script:PythonPrefix = @()

function Find-Python {
    foreach ($candidate in @("py", "python", "python3")) {
        if (-not (Get-Command $candidate -ErrorAction SilentlyContinue)) { continue }
        try {
            if ($candidate -eq "py") {
                & py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" 2>$null
                if ($LASTEXITCODE -eq 0) {
                    $script:PythonExe = "py"
                    $script:PythonPrefix = @("-3.12")
                    return $true
                }
            } else {
                & $candidate -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" 2>$null
                if ($LASTEXITCODE -eq 0) {
                    $script:PythonExe = $candidate
                    $script:PythonPrefix = @()
                    return $true
                }
            }
        } catch {
            continue
        }
    }
    return $false
}

function Invoke-HostPython {
    param([Parameter(ValueFromRemainingArguments = $true)][object[]]$PythonArgs)
    & $script:PythonExe @($script:PythonPrefix + $PythonArgs)
}

if (-not (Find-Python)) {
    Die "Python 3.12+ is required. Install it from https://www.python.org/downloads/ (check 'Add python.exe to PATH'), then retry."
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Die "Node.js 20+ (with npm) is required. Install it from https://nodejs.org/ then retry."
}

$nodeMajor = [int]((node -p "process.versions.node.split('.')[0]").Trim())
if ($nodeMajor -lt 20) {
    $nodeVersion = (node -v).Trim()
    Die "Node.js 20+ is required (found $nodeVersion). Upgrade from https://nodejs.org/"
}

$pythonVersion = (Invoke-HostPython --version 2>&1 | Out-String).Trim()
$nodeVersion = (node -v).Trim()
Write-Info "Using $pythonVersion and Node $nodeVersion"

# --- Backend setup -----------------------------------------------------------

$BackendDir = Join-Path $Root "backend"
$VenvDir = Join-Path $BackendDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

$needVenv = $false
if (-not (Test-Path $VenvPython)) {
    $needVenv = $true
} else {
    & $VenvPython -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Info "Existing virtualenv is below Python 3.12 — recreating…"
        Remove-Item -Recurse -Force $VenvDir
        $needVenv = $true
    }
}

if ($needVenv) {
    Write-Info "Creating Python virtual environment…"
    Invoke-HostPython -m venv $VenvDir
}

Write-Info "Installing backend dependencies…"
& $VenvPython -m pip install --upgrade pip | Out-Null
& $VenvPython -m pip install -e $BackendDir | Out-Null

# --- Frontend setup ----------------------------------------------------------

$FrontendDir = Join-Path $Root "frontend"
$EnvLocal = Join-Path $FrontendDir ".env.local"
$EnvExample = Join-Path $FrontendDir ".env.example"
if (-not (Test-Path $EnvLocal) -and (Test-Path $EnvExample)) {
    Copy-Item $EnvExample $EnvLocal
    Write-Info "Created frontend/.env.local from .env.example"
}

Write-Info "Installing frontend dependencies…"
Push-Location $FrontendDir
try {
    npm install
    if ($LASTEXITCODE -ne 0) { Die "npm install failed." }
} finally {
    Pop-Location
}

if ($Setup) {
    Write-Info "Setup complete. Run .\start.ps1 to launch the app."
    exit 0
}

# --- Start servers -----------------------------------------------------------

Write-Info "Starting backend on http://localhost:8000 …"
$backend = Start-Process -FilePath $VenvPython `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $BackendDir `
    -PassThru `
    -NoNewWindow

Write-Info "Starting frontend on http://localhost:3000 …"
if (-not $env:NEXT_PUBLIC_API_URL) {
    $env:NEXT_PUBLIC_API_URL = "http://localhost:8000"
}

# npm is a .cmd shim on Windows — invoke via cmd.exe
$frontend = Start-Process -FilePath "cmd.exe" `
    -ArgumentList @("/c", "npm", "run", "dev", "--", "--hostname", "127.0.0.1", "--port", "3000") `
    -WorkingDirectory $FrontendDir `
    -PassThru `
    -NoNewWindow

Write-Host ""
Write-Host "relax is starting."
Write-Host ""
Write-Host "  App:      http://localhost:3000"
Write-Host "  Calc:     http://localhost:3000/calc"
Write-Host "  API docs: http://localhost:8000/docs"
Write-Host ""
Write-Host "Press Ctrl+C to stop both servers."
Write-Host ""

try {
    while ($true) {
        if ($backend.HasExited -or $frontend.HasExited) {
            break
        }
        Start-Sleep -Seconds 1
    }
} finally {
    Write-Info "Shutting down…"
    foreach ($proc in @($backend, $frontend)) {
        if ($null -ne $proc -and -not $proc.HasExited) {
            # /T kills the process tree (npm → node, etc.)
            Start-Process -FilePath "taskkill.exe" `
                -ArgumentList @("/PID", "$($proc.Id)", "/T", "/F") `
                -Wait `
                -WindowStyle Hidden `
                -ErrorAction SilentlyContinue | Out-Null
        }
    }
}
