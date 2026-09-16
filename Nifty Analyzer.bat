@echo off
REM Launch Nifty Analyzer 2.0 (signal-only) from this folder.
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" desktop.py
  goto :eof
)

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py desktop.py
  goto :eof
)

python desktop.py
