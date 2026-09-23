# FRONTIER Windows Service Installer
# Run as Administrator

param(
    [string]$FrontierPath = $PSScriptRoot + "\..",
    [string]$PythonPath = ""
)

$FrontierPath = (Resolve-Path $FrontierPath).Path
$ServiceName = "FRONTIER"
$DisplayName = "FRONTIER AI Community Agent"
$Description = "Local AI agent for FRONTIER student tech community Discord server"

# Find Python if not specified
if (-not $PythonPath) {
    $PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $PythonPath) {
        $PythonPath = (Get-Command python3 -ErrorAction SilentlyContinue).Source
    }
}

if (-not $PythonPath) {
    Write-Error "Python not found. Install Python 3.11+ and try again."
    exit 1
}

Write-Host "FRONTIER installer" -ForegroundColor Cyan
Write-Host "Path: $FrontierPath" -ForegroundColor Gray
Write-Host "Python: $PythonPath" -ForegroundColor Gray

# Check .env exists
if (-not (Test-Path "$FrontierPath\.env")) {
    Write-Warning ".env not found. Copying .env.example..."
    Copy-Item "$FrontierPath\.env.example" "$FrontierPath\.env"
    Write-Host "Edit $FrontierPath\.env before starting the service." -ForegroundColor Yellow
}

# Install Python dependencies
Write-Host "`nInstalling Python dependencies..." -ForegroundColor Cyan
& $PythonPath -m pip install -r "$FrontierPath\requirements.txt" --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Error "pip install failed."
    exit 1
}

# Use NSSM (Non-Sucking Service Manager) if available, else Task Scheduler
$NssmPath = (Get-Command nssm -ErrorAction SilentlyContinue).Source

if ($NssmPath) {
    Write-Host "`nInstalling as Windows Service via NSSM..." -ForegroundColor Cyan

    & nssm install $ServiceName $PythonPath "$FrontierPath\run.py"
    & nssm set $ServiceName AppDirectory $FrontierPath
    & nssm set $ServiceName DisplayName $DisplayName
    & nssm set $ServiceName Description $Description
    & nssm set $ServiceName Start SERVICE_AUTO_START
    & nssm set $ServiceName AppStdout "$FrontierPath\logs\frontier.log"
    & nssm set $ServiceName AppStderr "$FrontierPath\logs\frontier-error.log"
    & nssm set $ServiceName AppRotateFiles 1
    & nssm set $ServiceName AppRotateSeconds 86400

    Write-Host "`nService installed. To start: nssm start $ServiceName" -ForegroundColor Green
    Write-Host "Or run: scripts\start.ps1" -ForegroundColor Gray

} else {
    Write-Host "`nNSSM not found. Installing via Task Scheduler..." -ForegroundColor Yellow
    Write-Host "  (For a proper Windows service, install NSSM: https://nssm.cc/download)" -ForegroundColor Gray

    $TaskName = "FRONTIER"
    $Action = New-ScheduledTaskAction `
        -Execute $PythonPath `
        -Argument "$FrontierPath\run.py" `
        -WorkingDirectory $FrontierPath

    $Trigger = New-ScheduledTaskTrigger -AtLogOn
    $Settings = New-ScheduledTaskSettingsSet `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -MultipleInstances IgnoreNew

    $Principal = New-ScheduledTaskPrincipal `
        -UserId $env:USERNAME `
        -LogonType Interactive `
        -RunLevel Highest

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Description $Description `
        -Force | Out-Null

    Write-Host "`nTask Scheduler entry created: FRONTIER" -ForegroundColor Green
    Write-Host "FRONTIER will start automatically on next login." -ForegroundColor Cyan
}

# Create start/stop shortcuts on Desktop
$WshShell = New-Object -comObject WScript.Shell

$StartLink = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\FRONTIER Start.lnk")
$StartLink.TargetPath = "powershell.exe"
$StartLink.Arguments = "-ExecutionPolicy Bypass -File `"$FrontierPath\scripts\start.ps1`""
$StartLink.WorkingDirectory = $FrontierPath
$StartLink.IconLocation = "powershell.exe,0"
$StartLink.Save()

$StopLink = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\FRONTIER Stop.lnk")
$StopLink.TargetPath = "powershell.exe"
$StopLink.Arguments = "-ExecutionPolicy Bypass -File `"$FrontierPath\scripts\stop.ps1`""
$StopLink.WorkingDirectory = $FrontierPath
$StopLink.IconLocation = "powershell.exe,0"
$StopLink.Save()

Write-Host "`n✅ FRONTIER installation complete!" -ForegroundColor Green
Write-Host "Desktop shortcuts created: FRONTIER Start / FRONTIER Stop" -ForegroundColor Cyan
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "  1. Edit .env with your Discord bot token and Ollama model"
Write-Host "  2. Make sure Ollama is running: ollama serve"
Write-Host "  3. Run: scripts\start.ps1"
Write-Host "  4. Open dashboard: http://localhost:8000/docs"
