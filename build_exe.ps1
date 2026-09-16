<#
  Build dist\NiftyAnalyzer\ (PyInstaller onedir) for the Command Desk.
  Run from the repo root on Windows with Python 3.12+.
#>
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = (Get-Command py -ErrorAction SilentlyContinue)
if ($py) { $python = "py" } else { $python = "python" }

& $python -m pip install -r requirements.txt -r requirements-build.txt
& $python -m PyInstaller --noconfirm --clean NiftyAnalyzer.spec

Write-Host "Built dist\NiftyAnalyzer\NiftyAnalyzer.exe"
Write-Host "Next: .\build_installer.ps1   (needs Inno Setup 6)"
