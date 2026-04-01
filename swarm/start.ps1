# ╔══════════════════════════════════════════════════════════════════╗
# ║  S.W.A.R.M. OS — Windows Quick Start                            ║
# ║  One command: venv → deps → server → seed → browser              ║
# ╚══════════════════════════════════════════════════════════════════╝
#
# Usage:  .\swarm\start.ps1
#         .\swarm\start.ps1 -Port 8001
#         .\swarm\start.ps1 -SkipSeed
param(
    [int]$Port = 8000,
    [switch]$SkipSeed
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $Root) { $Root = Split-Path -Parent $PSScriptRoot }
$SwarmDir = Join-Path $Root "swarm"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  S.W.A.R.M. QUANTUM SINGULARITY CANVAS                      ║" -ForegroundColor Green
Write-Host "║  Sovereign AGI OS v3.2.0 — Tarik Skalic, Bihac, Bosnia      ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

# ── 1. Check Python ──────────────────────────────────────────────
Write-Host "[1/5] Checking Python..." -ForegroundColor Cyan
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "ERROR: Python not found. Install Python 3.10+ first." -ForegroundColor Red
    exit 1
}
$pyVer = python --version 2>&1
Write-Host "  Found: $pyVer" -ForegroundColor DarkGray

# ── 2. Create/activate venv ──────────────────────────────────────
$VenvDir = Join-Path $Root ".venv"
Write-Host "[2/5] Virtual environment..." -ForegroundColor Cyan
if (-not (Test-Path (Join-Path $VenvDir "Scripts\python.exe"))) {
    Write-Host "  Creating venv at $VenvDir..." -ForegroundColor DarkGray
    python -m venv $VenvDir
}
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
Write-Host "  Using: $VenvPython" -ForegroundColor DarkGray

# ── 3. Install deps ─────────────────────────────────────────────
Write-Host "[3/5] Installing dependencies..." -ForegroundColor Cyan
& $VenvPython -m pip install --quiet --upgrade pip 2>&1 | Out-Null
& $VenvPython -m pip install --quiet -r (Join-Path $SwarmDir "requirements.txt") 2>&1 | Out-Null
Write-Host "  Done." -ForegroundColor DarkGray

# ── 4. Start server ─────────────────────────────────────────────
Write-Host "[4/5] Starting server on port $Port..." -ForegroundColor Cyan
$serverScript = Join-Path $SwarmDir "server.py"
$job = Start-Job -ScriptBlock {
    param($py, $script, $port)
    & $py $script --port $port
} -ArgumentList $VenvPython, $serverScript, $Port

# Wait for server to be ready
$ready = $false
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep 1
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:$Port/health" -TimeoutSec 2 -ErrorAction Stop
        $ready = $true
        break
    } catch {}
}

if (-not $ready) {
    Write-Host "  WARNING: Server may not be ready yet. Continuing..." -ForegroundColor Yellow
} else {
    Write-Host "  Server ready." -ForegroundColor DarkGray
}

# ── 5. Seed data ────────────────────────────────────────────────
if (-not $SkipSeed) {
    Write-Host "[5/5] Seeding demo data..." -ForegroundColor Cyan
    $seedScript = Join-Path $SwarmDir "demo_seed.py"
    & $VenvPython $seedScript 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
} else {
    Write-Host "[5/5] Skipping seed (use -SkipSeed to skip)." -ForegroundColor DarkGray
}

# ── Done ─────────────────────────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  SINGULARITY LIVE" -ForegroundColor Green
Write-Host "  Canvas:   http://localhost:$Port/" -ForegroundColor White
Write-Host "  Ingest:   POST http://localhost:$Port/ingest" -ForegroundColor DarkGray
Write-Host "  Graph:    GET  http://localhost:$Port/graph" -ForegroundColor DarkGray
Write-Host "  Spectral: GET  http://localhost:$Port/spectral" -ForegroundColor DarkGray
Write-Host "  REM:      POST http://localhost:$Port/rem" -ForegroundColor DarkGray
Write-Host "  Health:   GET  http://localhost:$Port/health" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Server PID: $($job.Id)  (Stop-Job $($job.Id) to halt)" -ForegroundColor DarkGray
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""

# Open browser
Start-Process "http://localhost:$Port/"
Write-Host "Press Ctrl+C to stop the server." -ForegroundColor Yellow

# Keep alive — relay server output
try {
    while ($true) {
        Receive-Job $job -ErrorAction SilentlyContinue | Write-Host
        Start-Sleep 2
    }
} finally {
    Stop-Job $job -ErrorAction SilentlyContinue
    Remove-Job $job -ErrorAction SilentlyContinue
    Write-Host "`nServer stopped." -ForegroundColor Red
}
