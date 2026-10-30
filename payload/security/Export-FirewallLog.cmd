@echo off
wevtutil qe Security /q:"*[System[(EventID=5157 or EventID=5152)]]" /c:5000 /rd:true /f:text > %~dp0logs\fw-blocked.txt
wevtutil qe Security /q:"*[System[(EventID=5156)]]" /c:5000 /rd:true /f:text > %~dp0logs\fw-allowed.txt
copy /y C:\Windows\System32\LogFiles\Firewall\pfirewall.log %~dp0logs\pfirewall-copy.log
echo Done. You can close this window.
pause

