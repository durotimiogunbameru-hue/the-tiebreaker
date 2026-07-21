# The Tiebreaker — one-command launcher (Windows / PowerShell)
# Creates a virtual environment, installs dependencies, and starts the server.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host "The Tiebreaker - setup + launch" -ForegroundColor Yellow

# 1. Virtual environment
$venv = Join-Path $root ".venv"
if (-not (Test-Path $venv)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    py -3 -m venv $venv
}
$py = Join-Path $venv "Scripts\python.exe"

# 2. Dependencies
Write-Host "Installing dependencies..." -ForegroundColor Cyan
& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet -r (Join-Path $root "backend\requirements.txt")

# 3. Load .env if present (so ANTHROPIC_API_KEY is picked up)
$envFile = Join-Path $root "backend\.env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]*)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            if ($name -and $value) { [Environment]::SetEnvironmentVariable($name, $value) }
        }
    }
    Write-Host "Loaded backend\.env" -ForegroundColor Cyan
}

# 4. Launch
if ($env:ANTHROPIC_API_KEY) {
    Write-Host "ANTHROPIC_API_KEY detected - running with real Claude analysis." -ForegroundColor Green
} else {
    Write-Host "No API key - running in deterministic demo (mock) mode." -ForegroundColor Yellow
}
Write-Host "Open http://localhost:8000 in your browser." -ForegroundColor Green

Set-Location (Join-Path $root "backend")
& $py -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
