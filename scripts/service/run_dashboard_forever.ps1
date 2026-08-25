# Auto-restart wrapper for the local dashboard. A shell:startup launcher runs
# this once (hidden, at logon) -- see BotFarmAutostart.vbs and
# docs/ARCHITECTURE.md (real Task Scheduler registration failed with Access
# Denied in the dev environment, so the Startup folder is used instead). This
# loops forever, restarting Flask if it ever crashes, and appends all output
# to logs/dashboard.log.
$ErrorActionPreference = "Continue"
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$script = Join-Path $root "scripts\run_dashboard.py"
$logDir = Join-Path $root "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$log = Join-Path $logDir "dashboard.log"

while ($true) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $log -Value "[$timestamp] Starting dashboard..." -Encoding utf8
    & $python $script *>> $log
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $log -Value "[$timestamp] Dashboard exited (code $LASTEXITCODE). Restarting in 10s..." -Encoding utf8
    Start-Sleep -Seconds 10
}
