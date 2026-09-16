<#
.SYNOPSIS
  Remove Start Menu / Desktop shortcuts and the in-place .venv.
  Does not delete this source folder or %APPDATA%\NiftyAnalyzer.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Product = "Nifty Analyzer"
$InstallRoot = $PSScriptRoot
$StartLink = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\$Product.lnk"
$Desktop = [Environment]::GetFolderPath("Desktop")
if (-not $Desktop) { $Desktop = Join-Path $env:USERPROFILE "Desktop" }
$DeskLink = Join-Path $Desktop "$Product.lnk"
$DeskBat = Join-Path $Desktop "$Product.bat"

foreach ($p in @($StartLink, $DeskLink, $DeskBat)) {
    if (Test-Path $p) {
        Remove-Item $p -Force
        Write-Host "Removed $p"
    }
}

$venv = Join-Path $InstallRoot ".venv"
if (Test-Path $venv) {
    Remove-Item $venv -Recurse -Force
    Write-Host "Removed $venv"
}

$stamp = Join-Path $InstallRoot "install.json"
if (Test-Path $stamp) {
    Remove-Item $stamp -Force
}

$appdataCopy = Join-Path $env:LOCALAPPDATA "NiftyAnalyzer"
if (Test-Path (Join-Path $appdataCopy "install.json")) {
    $meta = Get-Content (Join-Path $appdataCopy "install.json") -Raw | ConvertFrom-Json
    if (-not $meta.inPlace) {
        Remove-Item $appdataCopy -Recurse -Force
        Write-Host "Removed $appdataCopy"
    }
}

Write-Host "Kept this folder and %APPDATA%\NiftyAnalyzer (config + database)."
