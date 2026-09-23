# FRONTIER Start Script
param(
    [switch]$Background,
    [switch]$SkipNetworkWait
)

$FrontierPath = (Resolve-Path "$PSScriptRoot\..").Path
$EnvFile = "$FrontierPath\.env"
$LogFile = "$FrontierPath\logs\frontier.log"
$PidFile = "$FrontierPath\logs\frontier.pid"

# Ensure logs dir
if (-not (Test-Path "$FrontierPath\logs")) {
    New-Item -ItemType Directory -Path "$FrontierPath\logs" | Out-Null
}

# Check .env
if (-not (Test-Path $EnvFile)) {
    Write-Error ".env not found at $EnvFile. Run install-service.ps1 first."
    exit 1
}

# Check if already running
if (Test-Path $PidFile) {
    $existingPid = Get-Content $PidFile -ErrorAction SilentlyContinue
    if ($existingPid) {
        $proc = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "FRONTIER is already running (PID $existingPid)" -ForegroundColor Yellow
            Write-Host "Dashboard: http://localhost:8000/docs" -ForegroundColor Cyan
            exit 0
        }
    }
}

# Find Python
$PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonPath) { $PythonPath = (Get-Command python3 -ErrorAction SilentlyContinue).Source }
if (-not $PythonPath) { Write-Error "Python not found."; exit 1 }

Write-Host "🤖 Starting FRONTIER..." -ForegroundColor Cyan

if ($Background) {
    $proc = Start-Process `
        -FilePath $PythonPath `
        -ArgumentList "$FrontierPath\run.py" `
        -WorkingDirectory $FrontierPath `
        -RedirectStandardOutput $LogFile `
        -RedirectStandardError "$FrontierPath\logs\frontier-error.log" `
        -WindowStyle Hidden `
        -PassThru

    $proc.Id | Set-Content $PidFile
    Write-Host "✅ FRONTIER started in background (PID $($proc.Id))" -ForegroundColor Green
    Write-Host "Dashboard: http://localhost:8000/docs" -ForegroundColor Cyan
    Write-Host "Logs: $LogFile" -ForegroundColor Gray
} else {
    # Foreground with live output
    Set-Location $FrontierPath
    & $PythonPath run.py
}
