# Auto-restart wrapper for the paper-trading runner. Task Scheduler launches
# this once (hidden, at logon); it loops forever, restarting the Python
# process if it ever crashes, and appends all output to logs/paper_trading.log.
$ErrorActionPreference = "Continue"
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$script = Join-Path $root "scripts\run_paper_trading.py"
$log = Join-Path $root "logs\paper_trading.log"

while ($true) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $log -Value "[$timestamp] Starting paper trading runner..."
    & $python $script *>> $log
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $log -Value "[$timestamp] Paper trading runner exited (code $LASTEXITCODE). Restarting in 10s..."
    Start-Sleep -Seconds 10
}
