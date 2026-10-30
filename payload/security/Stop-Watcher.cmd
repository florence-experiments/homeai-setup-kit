@echo off
rem Stops the watcher until the next logon (or until Start-Watcher.cmd). Nothing is uninstalled.
setlocal
set "PY=%~dp0..\..\python\python.exe"
"%PY%" "%~dp0wctl.py" stop
if errorlevel 1 schtasks /End /TN "Security Watcher"
pause
