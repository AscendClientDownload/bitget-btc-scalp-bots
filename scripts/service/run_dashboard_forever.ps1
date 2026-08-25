# Auto-restart wrapper for the local dashboard. Task Scheduler launches this
# once (hidden, at logon); it loops forever, restarting Flask if it ever
# crashes, and appends all output to logs/dashboard.log.
$ErrorActionPreference = "Continue"
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$script = Join-Path $root "scripts\run_dashboard.py"
$log = Join-Path $root "logs\dashboard.log"

while ($true) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $log -Value "[$timestamp] Starting dashboard..."
    & $python $script *>> $log
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $log -Value "[$timestamp] Dashboard exited (code $LASTEXITCODE). Restarting in 10s..."
    Start-Sleep -Seconds 10
}
