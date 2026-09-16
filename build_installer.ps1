<#
  Compile NiftyAnalyzer-Setup-2.0.0.exe with Inno Setup 6.
  Requires: .\build_exe.ps1 already produced dist\NiftyAnalyzer\
#>
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$iss = Join-Path $PSScriptRoot "installer\NiftyAnalyzer.iss"
if (-not (Test-Path (Join-Path $PSScriptRoot "dist\NiftyAnalyzer\NiftyAnalyzer.exe"))) {
    Write-Host "Running build_exe.ps1 first…"
    & .\build_exe.ps1
}

$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $iscc) {
    throw "Inno Setup 6 not found. Install from https://jrsoftware.org/isinfo.php then re-run."
}

New-Item -ItemType Directory -Force -Path "dist\windows" | Out-Null
& $iscc $iss
Write-Host "Installer: dist\windows\NiftyAnalyzer-Setup-2.0.0.exe"
