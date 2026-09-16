@echo off
REM Launch Nifty Analyzer 2.0 (signal-only) from this folder.
cd /d "%~dp0"
if exist "Launch-NiftyAnalyzer.vbs" (
  wscript //nologo "%~dp0Launch-NiftyAnalyzer.vbs"
  goto :eof
)
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" desktop.py
  goto :eof
)
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" desktop.py
  goto :eof
)
python desktop.py
