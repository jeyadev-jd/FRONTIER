# FRONTIER Quick Setup
# Run from the FRONTIER directory: .\scripts\setup.ps1

$FrontierPath = (Resolve-Path "$PSScriptRoot\..").Path

Write-Host "⚡ FRONTIER Setup" -ForegroundColor Cyan
Write-Host "Path: $FrontierPath" -ForegroundColor Gray

# Python check
$PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonPath) {
    Write-Error "Python 3.11+ required. Download from https://python.org"
    exit 1
}
$version = & $PythonPath --version
Write-Host "Python: $version" -ForegroundColor Gray

# Create venv
if (-not (Test-Path "$FrontierPath\.venv")) {
    Write-Host "`nCreating virtual environment..." -ForegroundColor Cyan
    & $PythonPath -m venv "$FrontierPath\.venv"
}

$venvPython = "$FrontierPath\.venv\Scripts\python.exe"

# Install deps
Write-Host "Installing Python dependencies..." -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install -r "$FrontierPath\requirements.txt"

# Copy .env if needed
if (-not (Test-Path "$FrontierPath\.env")) {
    Copy-Item "$FrontierPath\.env.example" "$FrontierPath\.env"
    Write-Host "`n⚠️  Created .env from .env.example" -ForegroundColor Yellow
    Write-Host "   Edit $FrontierPath\.env with your settings before running." -ForegroundColor Yellow
}

# Node/npm check for dashboard
$npmPath = (Get-Command npm -ErrorAction SilentlyContinue).Source
if ($npmPath) {
    Write-Host "`nInstalling dashboard dependencies..." -ForegroundColor Cyan
    Set-Location "$FrontierPath\dashboard"
    & npm install --silent
    Set-Location $FrontierPath
} else {
    Write-Host "`nNode.js not found — skipping dashboard install." -ForegroundColor Yellow
    Write-Host "Install Node.js to use the dashboard: https://nodejs.org" -ForegroundColor Gray
}

# Ensure logs dir
New-Item -ItemType Directory -Force -Path "$FrontierPath\logs" | Out-Null

Write-Host "`n✅ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Edit .env — add DISCORD_BOT_TOKEN, DISCORD_GUILD_ID, OLLAMA_MODEL"
Write-Host "  2. Make sure Ollama is running: ollama serve"
Write-Host "  3. Start FRONTIER:"
Write-Host "     .\.venv\Scripts\python.exe run.py"
Write-Host "  4. Open API docs: http://localhost:8000/docs"
Write-Host "  5. Start dashboard (separate terminal):"
Write-Host "     cd dashboard && npm run dev"
Write-Host ""
Write-Host "Or install as background service: .\scripts\install-service.ps1" -ForegroundColor Cyan
