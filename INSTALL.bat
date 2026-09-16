@echo off
title Nifty Analyzer 2.0 — install in this folder
cd /d "%~dp0"
echo.
echo  Installing Nifty Analyzer in:
echo    %CD%
echo.
echo  This creates a virtualenv here and a Desktop app shortcut.
echo  SIGNAL-ONLY — this app never places broker orders.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Launch
if errorlevel 1 (
  echo.
  echo  Install failed. Install Python 3.12+ from https://www.python.org/downloads/
  echo  and tick "Add python.exe to PATH", then run this again.
  echo.
  pause
  exit /b 1
)
echo.
pause
