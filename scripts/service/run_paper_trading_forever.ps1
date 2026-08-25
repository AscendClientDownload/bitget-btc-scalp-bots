# Auto-restart wrapper for the paper-trading runner. A shell:startup launcher
# runs this once (hidden, at logon) -- see BotFarmAutostart.vbs and
# docs/ARCHITECTURE.md (real Task Scheduler registration failed with Access
# Denied in the dev environment, so the Startup folder is used instead). This
# loops forever, restarting the Python process if it ever crashes, and
# appends all output to logs/paper_trading.log.
#
# Runs scripts/run_all_bots.py (bot01 + all 100 catalog strategies in one
# process) rather than the single-bot scripts/run_paper_trading.py.
$ErrorActionPreference = "Continue"
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$script = Join-Path $root "scripts\run_all_bots.py"
$logDir = Join-Path $root "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$log = Join-Path $logDir "paper_trading.log"

while ($true) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $log -Value "[$timestamp] Starting paper trading runner..." -Encoding utf8
    & $python $script *>> $log
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $log -Value "[$timestamp] Paper trading runner exited (code $LASTEXITCODE). Restarting in 10s..." -Encoding utf8
    Start-Sleep -Seconds 10
}
