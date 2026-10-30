@echo off
rem Use this after YOU change HomeAI presets/settings on purpose.
rem It records the current files as the new "known good" (hashes + .good copies; old .good copies are kept as .bak).
rem For a single file you can instead click "This change was me" on the alert.
setlocal
set "PY=%~dp0..\..\python\python.exe"
echo This makes the CURRENT presets.json and settings.json the new known-good versions.
choice /M "Continue"
if errorlevel 2 exit /b 0
"%PY%" "%~dp0wctl.py" baseline --refresh-good
pause
