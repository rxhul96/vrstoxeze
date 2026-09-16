<# One-shot: PyInstaller onedir + Inno Setup exe. #>
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
& .\build_exe.ps1
& .\build_installer.ps1
