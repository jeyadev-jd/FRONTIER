# FRONTIER Stop Script
$FrontierPath = (Resolve-Path "$PSScriptRoot\..").Path
$PidFile = "$FrontierPath\logs\frontier.pid"

if (Test-Path $PidFile) {
    $pid = Get-Content $PidFile -ErrorAction SilentlyContinue
    if ($pid) {
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id $pid -Force
            Write-Host "✅ FRONTIER stopped (PID $pid)" -ForegroundColor Green
        } else {
            Write-Host "FRONTIER not running (stale PID file)" -ForegroundColor Yellow
        }
        Remove-Item $PidFile -ErrorAction SilentlyContinue
    }
} else {
    # Try killing by process name
    $procs = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
        $_.MainModule.FileName -like "*FRONTIER*" -or
        ($_.CommandLine -like "*run.py*" -and $_.CommandLine -like "*FRONTIER*")
    }
    if ($procs) {
        $procs | Stop-Process -Force
        Write-Host "✅ FRONTIER stopped" -ForegroundColor Green
    } else {
        Write-Host "FRONTIER is not running" -ForegroundColor Yellow
    }
}
