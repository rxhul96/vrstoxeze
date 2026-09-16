<#
  Compile NiftyAnalyzer-Setup-2.0.0.exe with Inno Setup 6 (ISCC).
#>
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$exe = Join-Path $PSScriptRoot "dist\NiftyAnalyzer\NiftyAnalyzer.exe"
if (-not (Test-Path $exe)) {
    Write-Host "App payload missing — running build_exe.ps1"
    & .\build_exe.ps1
}

function Find-ISCC {
    $candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($p in $candidates) {
        if ($p -and (Test-Path $p)) { return $p }
    }
    $cmd = Get-Command iscc -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $cmd = Get-Command ISCC -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

$iscc = Find-ISCC
if (-not $iscc) {
    throw @"
Inno Setup 6 compiler (ISCC.exe) was not found.
Install from https://jrsoftware.org/isinfo.php
Typical path: C:\Program Files (x86)\Inno Setup 6\ISCC.exe
"@
}

Write-Host "Compiling Setup.exe with $iscc"
New-Item -ItemType Directory -Force -Path "dist\windows" | Out-Null
& $iscc (Join-Path $PSScriptRoot "installer\NiftyAnalyzer.iss")
if ($LASTEXITCODE -ne 0) { throw "ISCC failed" }

$setup = Join-Path $PSScriptRoot "dist\windows\NiftyAnalyzer-Setup-2.0.0.exe"
if (-not (Test-Path $setup)) { throw "ISCC did not produce $setup" }

Write-Host ""
Write-Host "Installer ready:" -ForegroundColor Green
Write-Host "  $setup"
Write-Host "Double-click that file to install Nifty Analyzer (no Python needed)."
