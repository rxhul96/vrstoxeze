<#
  One-shot Windows build: PyInstaller payload + Inno Setup Setup.exe
  Double-click Build-Setup.bat or run:  powershell -ExecutionPolicy Bypass -File .\build_windows.ps1
#>
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Write-Host "=== Nifty Analyzer 2.0 — full Setup.exe ===" -ForegroundColor Cyan
& .\build_exe.ps1
if ($LASTEXITCODE -ne 0) { throw "build_exe.ps1 failed" }
& .\build_installer.ps1
if ($LASTEXITCODE -ne 0) { throw "build_installer.ps1 failed" }
$setup = Join-Path $PSScriptRoot "dist\windows\NiftyAnalyzer-Setup-2.0.0.exe"
if (Test-Path $setup) {
    Write-Host ""
    Write-Host "DONE. Install with:" -ForegroundColor Green
    Write-Host "  $setup"
    try { Invoke-Item (Split-Path $setup) } catch { }
}
