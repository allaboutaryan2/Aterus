@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" desktop.py
) else (
  py -3 desktop.py
  if errorlevel 1 pause
)
