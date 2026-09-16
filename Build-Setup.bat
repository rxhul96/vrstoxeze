@echo off
REM Double-click this file on Windows to build NiftyAnalyzer-Setup-2.0.0.exe
REM Needs: Python 3.12+ and Inno Setup 6 (ISCC.exe)
cd /d "%~dp0"
title Building Nifty Analyzer Setup.exe
echo.
echo Building a full self-contained installer (no Python required to INSTALL).
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows.ps1"
if errorlevel 1 (
  echo.
  echo BUILD FAILED.
  pause
  exit /b 1
)
echo.
if exist "%~dp0dist\windows\NiftyAnalyzer-Setup-2.0.0.exe" (
  echo Installer:
  echo   %~dp0dist\windows\NiftyAnalyzer-Setup-2.0.0.exe
  echo Double-click that file to install Nifty Analyzer.
)
echo.
pause
