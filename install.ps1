<#
.SYNOPSIS
  Install Nifty Analyzer 2.0 (Institutional Command Desk) for the current Windows user.

.DESCRIPTION
  Copies the app into %LOCALAPPDATA%\NiftyAnalyzer, creates a venv, installs
  dependencies, writes %APPDATA%\NiftyAnalyzer\.env on first run, and adds
  Start Menu (and optional Desktop) shortcuts.

  This is a SIGNAL-ONLY install. It cannot place, modify, or cancel orders.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\install.ps1
  powershell -ExecutionPolicy Bypass -File .\install.ps1 -DesktopShortcut
#>
[CmdletBinding()]
param(
    [switch]$DesktopShortcut,
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$Version = "2.0.0"
$Product = "Nifty Analyzer"
$Source = $PSScriptRoot
$InstallRoot = Join-Path $env:LOCALAPPDATA "NiftyAnalyzer"
$UserData = Join-Path $env:APPDATA "NiftyAnalyzer"
$StartMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"

function Find-Python {
    if ($Python -and (Test-Path $Python)) { return $Python }
    foreach ($cmd in @("py", "python", "python3")) {
        $hit = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($hit) { return $hit.Source }
    }
    throw "Python 3.12+ was not found. Install it from https://www.python.org/downloads/ and re-run install.ps1."
}

$py = Find-Python
Write-Host "Installing $Product $Version (signal-only Command Desk)" -ForegroundColor Cyan
Write-Host "  source : $Source"
Write-Host "  app    : $InstallRoot"
Write-Host "  data   : $UserData"

New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
New-Item -ItemType Directory -Force -Path $UserData | Out-Null

$copy = @("backend", "frontend", "assets", "deploy")
foreach ($name in $copy) {
    $src = Join-Path $Source $name
    if (Test-Path $src) {
        $dst = Join-Path $InstallRoot $name
        if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
        Copy-Item $src $dst -Recurse -Force
    }
}
foreach ($file in @("desktop.py", "requirements.txt", "requirements-desktop.txt", "README.md", "WINDOWS_SETUP.md")) {
    $src = Join-Path $Source $file
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $InstallRoot (Split-Path $file -Leaf)) -Force
    }
}

$envDefault = Join-Path $Source "assets\.env.default"
$userEnv = Join-Path $UserData ".env"
if (-not (Test-Path $userEnv)) {
    if (Test-Path $envDefault) {
        Copy-Item $envDefault $userEnv
        Write-Host "  wrote  : $userEnv (edit Kite keys here for live data)"
    }
} else {
    Write-Host "  kept   : existing $userEnv"
}

$venv = Join-Path $InstallRoot ".venv"
Write-Host "Creating virtualenv…"
& $py -m venv $venv
$venvPy = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $venvPy)) { throw "venv python missing at $venvPy" }

Write-Host "Installing packages…"
& $venvPy -m pip install --upgrade pip
& $venvPy -m pip install -r (Join-Path $InstallRoot "requirements.txt")
$deskReq = Join-Path $InstallRoot "requirements-desktop.txt"
if (Test-Path $deskReq) {
    & $venvPy -m pip install -r $deskReq
}

$venvPyw = Join-Path $venv "Scripts\pythonw.exe"
if (-not (Test-Path $venvPyw)) { $venvPyw = $venvPy }
$desktopPy = Join-Path $InstallRoot "desktop.py"

function New-Shortcut([string]$Path, [string]$Target, [string]$Arguments, [string]$WorkDir) {
    $w = New-Object -ComObject WScript.Shell
    $sc = $w.CreateShortcut($Path)
    $sc.TargetPath = $Target
    $sc.Arguments = '"' + $Arguments + '"'
    $sc.WorkingDirectory = $WorkDir
    $sc.WindowStyle = 7
    $sc.Description = "Nifty Analyzer 2.0 — signal-only Command Desk"
    $sc.Save()
}

New-Item -ItemType Directory -Force -Path $StartMenu | Out-Null
$startLink = Join-Path $StartMenu "$Product.lnk"
New-Shortcut $startLink $venvPyw $desktopPy $InstallRoot
Write-Host "  start  : $startLink"

if ($DesktopShortcut) {
    $deskLink = Join-Path ([Environment]::GetFolderPath("Desktop")) "$Product.lnk"
    New-Shortcut $deskLink $venvPyw $desktopPy $InstallRoot
    Write-Host "  desktop: $deskLink"
}

Copy-Item (Join-Path $Source "uninstall.ps1") (Join-Path $InstallRoot "uninstall.ps1") -Force -ErrorAction SilentlyContinue

$stamp = @{
    version = $Version
    installedAt = (Get-Date).ToString("o")
    source = $Source
    signalOnly = $true
} | ConvertTo-Json
Set-Content -Path (Join-Path $InstallRoot "install.json") -Value $stamp -Encoding UTF8

Write-Host ""
Write-Host "Installed $Product $Version." -ForegroundColor Green
Write-Host "Open it from the Start Menu (Nifty Analyzer)."
Write-Host "SIGNAL-ONLY MODE — automated trading is disabled."
Write-Host "Kite redirect URL: http://127.0.0.1:8000/kite/callback"
Write-Host "Config: $userEnv"
Write-Host "Uninstall: powershell -File `"$InstallRoot\uninstall.ps1`""
