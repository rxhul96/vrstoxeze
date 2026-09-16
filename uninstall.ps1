<#
.SYNOPSIS
  Remove a per-user Nifty Analyzer 2.0 install created by install.ps1.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$InstallRoot = Join-Path $env:LOCALAPPDATA "NiftyAnalyzer"
$StartLink = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Nifty Analyzer.lnk"
$DeskLink = Join-Path ([Environment]::GetFolderPath("Desktop")) "Nifty Analyzer.lnk"

foreach ($p in @($StartLink, $DeskLink)) {
    if (Test-Path $p) {
        Remove-Item $p -Force
        Write-Host "Removed $p"
    }
}

if (Test-Path $InstallRoot) {
    Remove-Item $InstallRoot -Recurse -Force
    Write-Host "Removed $InstallRoot"
}

Write-Host "Kept %APPDATA%\NiftyAnalyzer (your .env and session database)."
Write-Host "Delete that folder too if you want a completely clean slate."
