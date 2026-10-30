@echo off
rem Makes the watcher start by itself 30 seconds after you log on, with admin rights
rem (needed to read the Security log and to close programs). Run as administrator.
setlocal
set "HERE=%~dp0"
set "PYW=%~dp0..\..\python\pythonw.exe"
set "TN=Security Watcher"

net session >nul 2>&1
if errorlevel 1 (
  echo Run as administrator.
  if not defined NOPAUSE pause
  exit /b 1
)
schtasks /Create /F /TN "%TN%" /SC ONLOGON /DELAY 0000:30 /RL HIGHEST /IT /RU "%USERNAME%" /TR "\"%PYW%\" \"%HERE%watcher.py\""
if errorlevel 1 (
  echo Could not create the task.
  if not defined NOPAUSE pause
  exit /b 1
)
rem Remove the default 3-day time limit, keep running on battery, restart if it crashes.
powershell -NoProfile -Command "Set-ScheduledTask -TaskName '%TN%' -Settings (New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1))" >nul
schtasks /Run /TN "%TN%"
echo Watcher task installed and started. Monitor page: http://127.0.0.1:8095/
if not defined NOPAUSE pause
exit /b 0
