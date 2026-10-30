@echo off
rem Stops the watcher and removes its logon task. Files in this folder stay (delete the folder if you want).
rem Run as administrator.
setlocal
set "PY=%~dp0..\..\python\python.exe"
"%PY%" "%~dp0wctl.py" stop >nul 2>&1
schtasks /End /TN "Security Watcher" >nul 2>&1
schtasks /Delete /TN "Security Watcher" /F
pause
