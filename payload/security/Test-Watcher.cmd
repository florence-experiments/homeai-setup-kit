@echo off
rem Safe self-test. No admin needed. Nothing real is changed:
rem  - feeds 12 fake firewall lines (fake port scan from 203.0.113.x, a documentation-only address)
rem  - changes a TEMP COPY of presets.json (your real file is not touched)
rem  - starts a dummy python.exe that tries 1.1.1.1:443 and checks the watcher closes it
setlocal
set "PY=%~dp0..\..\python\python.exe"
"%PY%" "%~dp0wctl.py" test
pause
