# Security Monitor (optional HomeAI extra, Windows only)

A small background watcher that keeps an eye on your PC's network activity and on HomeAI's files, and shows a red
pop-up when something looks wrong. It starts by itself after you log on and has a Monitor page at
**http://127.0.0.1:8095/** that only this PC can open. It uses only Python's standard library and Windows' own tools.

## What it watches for

| What | What it does |
|---|---|
| An AI program (anything in your HomeAI folder, llama-server, Python, ComfyUI) connects to the internet without your approval | Closes that program and shows a pop-up |
| An AI program tries to reach the internet and the firewall blocks it | Closes it and shows a pop-up |
| Someone on the network connects into an AI server | Pop-up with a hint on how to fix it |
| Something that looks like a screenshot or screen capture | Pop-up (a best guess) |
| A port scan (one address trying 10+ ports within 60 seconds) | Pop-up with a **Block this IP** button |
| HomeAI's `presets.json` or `settings.json` changes | Pop-up with **Restore file** / **This change was me** (never restores by itself) |
| A program opening the Windows password process (lsass) or injecting code | Pop-up |

Your home network (192.168.x, 10.x, 172.16-31.x), the mesh-VPN range 100.64.0.0/10 and this PC count as safe.
Windows itself and Microsoft Defender are never closed. Add your own trusted programs to `never_kill` or
`allowed_apps` in `config.json`.

## Install

1. Right-click **Install-All.cmd** and choose **Run as administrator** (1-3 minutes). It downloads Sysmon from
   Microsoft Sysinternals (only installed if Microsoft's signature is valid), the sysmon-modular config from a fixed
   release (SHA-256 checked), and the free offline DB-IP Lite country files; makes the Security log bigger; records a
   baseline of HomeAI's presets/settings; and sets the watcher to start at logon.
2. Double-click **Test-Watcher.cmd**: three PASS lines and a few pop-ups marked TEST. The test uses fake data and a
   temporary copy of your presets.
3. Open http://127.0.0.1:8095/.

Before HomeAI needs the internet on purpose (setup, '+ Add mode', the Model Updater, web search), click
**Pause closing apps 30 min** on the Monitor page. After adding a mode or changing presets, run
**Update-Baseline.cmd** so the change is recorded as yours.

## Privacy

Everything stays on this PC. No telemetry. Logs and state are kept in the `logs` and `state` folders here and
can be deleted at any time.

## Limits

Screen-capture detection is a best guess. It cannot stop a program that is already allowed. It is a helper, not a
replacement for Windows Security.

---
Built by Florence for the community.
