<#
  Build dist\NiftyAnalyzer\ (PyInstaller onedir) — self-contained, no Python required at runtime.
#>
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Get-Python {
    foreach ($c in @("py", "python", "python3")) {
        $hit = Get-Command $c -ErrorAction SilentlyContinue
        if ($hit) { return $hit.Source }
    }
    throw "Python 3.12+ is required to BUILD the installer (the Setup.exe you ship does not need Python)."
}

$python = Get-Python
Write-Host "Building NiftyAnalyzer.exe with $python"

if (Test-Path "scripts\generate_icon.py") {
    & $python "scripts\generate_icon.py"
}

& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt -r requirements-build.txt
& $python -m PyInstaller --noconfirm --clean NiftyAnalyzer.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$exe = Join-Path $PSScriptRoot "dist\NiftyAnalyzer\NiftyAnalyzer.exe"
if (-not (Test-Path $exe)) {
    throw "Expected $exe after PyInstaller"
}
Write-Host "OK $exe"
