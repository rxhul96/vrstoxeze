# Dev launcher (repo checkout). For a Start Menu install use .\install.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    Write-Host "Creating .venv…"
    py -m venv .venv 2>$null
    if (-not (Test-Path .\.venv\Scripts\python.exe)) { python -m venv .venv }
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    .\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
}

$env:MARKET_DATA_MODE = if ($env:MARKET_DATA_MODE) { $env:MARKET_DATA_MODE } else { "replay" }
.\.venv\Scripts\python.exe desktop.py @args
