# Start FRONTIER with system tray icon
$FrontierPath = (Resolve-Path "$PSScriptRoot\..").Path
$PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source

if (-not $PythonPath) {
    Write-Error "Python not found."
    exit 1
}

# Install tray dependencies if needed
& $PythonPath -m pip install pystray pillow --quiet

Start-Process `
    -FilePath $PythonPath `
    -ArgumentList "$FrontierPath\tray.py" `
    -WorkingDirectory $FrontierPath `
    -WindowStyle Hidden

Write-Host "✅ FRONTIER tray icon started" -ForegroundColor Green
