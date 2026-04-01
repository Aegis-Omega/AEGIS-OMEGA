# ╔══════════════════════════════════════════════════════════════════╗
# ║  S.W.A.R.M. OS — Deployment Pipeline                            ║
# ║  One command: test → commit → push → (Cloud Run if available)    ║
# ╚══════════════════════════════════════════════════════════════════╝
#
# Usage:  .\deploy.ps1
#         .\deploy.ps1 -SkipTests
#         .\deploy.ps1 -Message "fix: corrected dream state timing"
param(
    [string]$Message = "",
    [switch]$SkipTests,
    [switch]$SkipPush
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
if (-not $Root) { $Root = Get-Location }
$SwarmDir = Join-Path $Root "swarm"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  S.W.A.R.M. DEPLOY PIPELINE                              ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan

$steps = 0
$failed = $false

# ── 1. Smoke tests ───────────────────────────────────────────────
$steps++
if (-not $SkipTests) {
    Write-Host "`n[$steps] Running endpoint smoke tests..." -ForegroundColor Yellow
    $VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path $VenvPython)) { $VenvPython = "python" }

    $testResult = & $VenvPython (Join-Path $SwarmDir "test_endpoints.py") 2>&1
    $testResult | ForEach-Object { Write-Host "  $_" }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  TESTS FAILED — aborting deploy." -ForegroundColor Red
        exit 1
    }
    Write-Host "  Tests passed." -ForegroundColor Green
} else {
    Write-Host "`n[$steps] Skipping tests (--SkipTests)." -ForegroundColor DarkGray
}

# ── 2. Git status ────────────────────────────────────────────────
$steps++
Write-Host "`n[$steps] Checking git status..." -ForegroundColor Yellow
$status = git -C $Root status --porcelain 2>&1
if (-not $status) {
    Write-Host "  Working tree clean — nothing to commit." -ForegroundColor DarkGray
} else {
    $changeCount = ($status | Measure-Object -Line).Lines
    Write-Host "  $changeCount changed file(s)." -ForegroundColor DarkGray

    # Auto-generate commit message if not provided
    if (-not $Message) {
        $Message = "chore: update SWARM OS $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    }

    git -C $Root add .
    git -C $Root commit -m $Message
    Write-Host "  Committed: $Message" -ForegroundColor Green
}

# ── 3. Push to GitHub ────────────────────────────────────────────
$steps++
if (-not $SkipPush) {
    Write-Host "`n[$steps] Pushing to GitHub..." -ForegroundColor Yellow
    $remote = git -C $Root remote 2>&1
    if ($remote) {
        git -C $Root push 2>&1 | ForEach-Object { Write-Host "  $_" }
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  Pushed to origin." -ForegroundColor Green
        } else {
            Write-Host "  Push failed. You may need to configure auth:" -ForegroundColor Yellow
            Write-Host "    git remote add origin https://github.com/tarikskalic33/myapp.git" -ForegroundColor DarkGray
            Write-Host "    git push -u origin main" -ForegroundColor DarkGray
            $failed = $true
        }
    } else {
        Write-Host "  No remote configured. To add:" -ForegroundColor Yellow
        Write-Host "    git remote add origin https://github.com/tarikskalic33/myapp.git" -ForegroundColor DarkGray
        Write-Host "    git push -u origin main" -ForegroundColor DarkGray
    }
} else {
    Write-Host "`n[$steps] Skipping push (--SkipPush)." -ForegroundColor DarkGray
}

# ── 4. Cloud Run deploy ─────────────────────────────────────────
$steps++
Write-Host "`n[$steps] Cloud Run deploy..." -ForegroundColor Yellow
$gcloud = Get-Command gcloud -ErrorAction SilentlyContinue
if ($gcloud) {
    Write-Host "  gcloud found. Deploying to europe-west1..." -ForegroundColor Cyan
    gcloud run deploy swarm-manifold `
        --source $SwarmDir `
        --region europe-west1 `
        --project lifequestplatinum `
        --allow-unauthenticated `
        --port 8000 2>&1 | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host "  gcloud not available. To deploy manually:" -ForegroundColor DarkGray
    Write-Host "    gcloud run deploy swarm-manifold --source swarm/ --region europe-west1 --project lifequestplatinum" -ForegroundColor DarkGray
}

# ── Summary ──────────────────────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
if ($failed) {
    Write-Host "  DEPLOY COMPLETE (with warnings)" -ForegroundColor Yellow
} else {
    Write-Host "  DEPLOY COMPLETE" -ForegroundColor Green
}
$hash = git -C $Root log --oneline -1 2>&1
Write-Host "  Latest commit: $hash" -ForegroundColor DarkGray
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
