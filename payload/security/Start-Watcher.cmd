@echo off
rem Starts the watcher (through its logon task, so it gets admin rights) and opens the monitor page.
setlocal
set "PY=%~dp0..\..\python\python.exe"
schtasks /Run /TN "Security Watcher" >nul 2>&1
if errorlevel 1 (
  echo The "Security Watcher" task is not installed - run Install-All.cmd as administrator first.
  pause
  exit /b 1
)
timeout /t 5 /nobreak >nul
"%PY%" "%~dp0wctl.py" status
start "" http://127.0.0.1:8095/
pause
