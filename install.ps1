<#
.SYNOPSIS
  Install Nifty Analyzer 2.0 in THIS folder and put a Desktop app shortcut there.

.DESCRIPTION
  In-place install: venv + packages live next to this script (the repo,
  e.g. D:\Trading\vrstoxeze-1). Always creates a Desktop shortcut named
  "Nifty Analyzer" with the app icon. Double-click INSTALL.bat instead
  of running this by hand.

  SIGNAL-ONLY. Cannot place, modify, or cancel orders.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\install.ps1
.EXAMPLE
  .\install.ps1 -Launch
#>
[CmdletBinding()]
param(
    [switch]$NoDesktopShortcut,
    [switch]$Launch,
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$Version = "2.0.0"
$Product = "Nifty Analyzer"
$InstallRoot = $PSScriptRoot
$UserData = Join-Path $env:APPDATA "NiftyAnalyzer"
$StartMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$Desktop = [Environment]::GetFolderPath("Desktop")
if (-not $Desktop) { $Desktop = Join-Path $env:USERPROFILE "Desktop" }

function Find-Python {
    if ($Python -and (Test-Path $Python)) { return $Python }
    foreach ($cmd in @("py", "python", "python3")) {
        $hit = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($hit) { return $hit.Source }
    }
    throw "Python 3.12+ was not found. Install it from https://www.python.org/downloads/ (tick Add python.exe to PATH) and re-run INSTALL.bat."
}

$py = Find-Python
Write-Host "Installing $Product $Version IN PLACE (signal-only Command Desk)" -ForegroundColor Cyan
Write-Host "  app    : $InstallRoot"
Write-Host "  data   : $UserData"
Write-Host "  desktop: $Desktop"

New-Item -ItemType Directory -Force -Path $UserData | Out-Null

$envDefault = Join-Path $InstallRoot "assets\.env.default"
$userEnv = Join-Path $UserData ".env"
if (-not (Test-Path $userEnv)) {
    if (Test-Path $envDefault) {
        Copy-Item $envDefault $userEnv
        Write-Host "  wrote  : $userEnv"
    }
} else {
    Write-Host "  kept   : $userEnv"
}

$venv = Join-Path $InstallRoot ".venv"
Write-Host "Creating virtualenv in this folder…"
& $py -m venv $venv
if ($LASTEXITCODE -ne 0) { throw "python -m venv failed (exit $LASTEXITCODE)" }
$venvPy = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $venvPy)) { throw "venv python missing at $venvPy" }

Write-Host "Installing packages (this can take a minute)…"
& $venvPy -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
& $venvPy -m pip install -r (Join-Path $InstallRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "pip install requirements.txt failed" }
$deskReq = Join-Path $InstallRoot "requirements-desktop.txt"
if (Test-Path $deskReq) {
    & $venvPy -m pip install -r $deskReq
    if ($LASTEXITCODE -ne 0) { throw "pip install requirements-desktop.txt failed" }
}

$vbs = Join-Path $InstallRoot "Launch-NiftyAnalyzer.vbs"
if (-not (Test-Path $vbs)) { throw "Launch-NiftyAnalyzer.vbs missing next to install.ps1" }
$wscript = Join-Path $env:SystemRoot "System32\wscript.exe"
if (-not (Test-Path $wscript)) { $wscript = "wscript.exe" }
$icon = Join-Path $InstallRoot "assets\nifty.ico"

function New-AppShortcut([string]$Path) {
    $w = New-Object -ComObject WScript.Shell
    $sc = $w.CreateShortcut($Path)
    $sc.TargetPath = $wscript
    $sc.Arguments = '//nologo "' + $vbs + '"'
    $sc.WorkingDirectory = $InstallRoot
    $sc.WindowStyle = 7
    $sc.Description = "Nifty Analyzer 2.0 — signal-only Command Desk"
    if (Test-Path $icon) { $sc.IconLocation = "$icon,0" }
    $sc.Save()
}

New-Item -ItemType Directory -Force -Path $StartMenu | Out-Null
$startLink = Join-Path $StartMenu "$Product.lnk"
New-AppShortcut $startLink
Write-Host "  start  : $startLink"

if (-not $NoDesktopShortcut) {
    $deskLink = Join-Path $Desktop "$Product.lnk"
    New-AppShortcut $deskLink
    Write-Host "  desktop: $deskLink"
}

$stamp = @{
    version     = $Version
    installedAt = (Get-Date).ToString("o")
    installRoot = $InstallRoot
    inPlace     = $true
    signalOnly  = $true
} | ConvertTo-Json
Set-Content -Path (Join-Path $InstallRoot "install.json") -Value $stamp -Encoding UTF8

Write-Host ""
Write-Host "Installed $Product $Version in this folder." -ForegroundColor Green
Write-Host "Desktop app: $Desktop\$Product.lnk"
Write-Host "SIGNAL-ONLY MODE — automated trading is disabled."
Write-Host "Kite redirect URL: http://127.0.0.1:8000/kite/callback"
Write-Host "Config: $userEnv"

if ($Launch) {
    Write-Host "Launching $Product…"
    Start-Process -FilePath $wscript -ArgumentList @("//nologo", $vbs) -WorkingDirectory $InstallRoot
}
