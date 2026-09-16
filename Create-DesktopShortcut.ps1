<# Create / refresh the Desktop "Nifty Analyzer" app shortcut for THIS folder. #>
$ErrorActionPreference = "Stop"
$Product = "Nifty Analyzer"
$InstallRoot = $PSScriptRoot
$Desktop = [Environment]::GetFolderPath("Desktop")
if (-not $Desktop) { $Desktop = Join-Path $env:USERPROFILE "Desktop" }

$vbs = Join-Path $InstallRoot "Launch-NiftyAnalyzer.vbs"
if (-not (Test-Path $vbs)) {
    throw "Launch-NiftyAnalyzer.vbs is missing. Keep it next to this script."
}
$wscript = Join-Path $env:SystemRoot "System32\wscript.exe"
if (-not (Test-Path $wscript)) { $wscript = "wscript.exe" }
$icon = Join-Path $InstallRoot "assets\nifty.ico"
$deskLink = Join-Path $Desktop "$Product.lnk"

$w = New-Object -ComObject WScript.Shell
$sc = $w.CreateShortcut($deskLink)
$sc.TargetPath = $wscript
$sc.Arguments = '//nologo "' + $vbs + '"'
$sc.WorkingDirectory = $InstallRoot
$sc.WindowStyle = 7
$sc.Description = "Nifty Analyzer 2.0 — signal-only Command Desk"
if (Test-Path $icon) { $sc.IconLocation = "$icon,0" }
$sc.Save()

Write-Host "Desktop app shortcut: $deskLink"
