"""Start/stop scripts in the HomeAI folder, plus desktop / start-menu shortcuts (Windows .lnk, Linux .desktop)."""
from __future__ import annotations

import os
import subprocess
import sys

from .components import write
from .util import IS_WIN, say

APPS = [  # (shortcut name, script base name, icon, component needed)
    ("HomeAI", "start-homeai", "homeai", None),
    ("Stop HomeAI", "stop-homeai", "stop", None),
    ("HomeAI - Add a mode", "add-mode", "add", None),
    ("HomeAI Model Updater", "model-updater", "updater", "updater"),
    ("HomeAI Security Monitor", "security-monitor", "security", "security"),
]


def write_scripts(root, comps):
    """Writes the small scripts that start/stop everything. Returns {base name: path}."""
    out = {}
    if IS_WIN:
        head = "@echo off\r\nset \"PYTHONPATH=%~dp0kit\"\r\n"
        py = "\"%~dp0python\\python.exe\""
        cmds = {"start-homeai": (head + py + " -m homeai_setup.control start\r\n"
                                 "if errorlevel 1 pause\r\n"),
                "stop-homeai": head + py + " -m homeai_setup.control stop\r\ntimeout /t 3 >nul\r\n",
                "add-mode": head + py + " -m homeai_setup.addmode\r\npause\r\n",
                "uninstall": head + py + " -m homeai_setup.uninstall\r\npause\r\n"}
        names = {"start-homeai": "Start HomeAI.cmd", "stop-homeai": "Stop HomeAI.cmd", "add-mode": "Add a mode.cmd",
                 "uninstall": "Uninstall HomeAI.cmd"}
        for k, text in cmds.items():
            p = os.path.join(root, names[k])
            write(p, text)
            out[k] = p
        if "updater" in comps:
            out["model-updater"] = os.path.join(root, "extras", "model-updater", "Run-Model-Updater.cmd")
        if "security" in comps:
            p = os.path.join(root, "extras", "security", "Open-Monitor.cmd")
            write(p, "@echo off\r\nstart \"\" http://127.0.0.1:8095/\r\n")
            out["security-monitor"] = p
    else:
        py = sys.executable
        cmds = {"start-homeai": "control start", "stop-homeai": "control stop", "add-mode": "addmode", "uninstall": "uninstall"}
        for k, sub in cmds.items():
            p = os.path.join(root, k + ".sh")
            write(p, "#!/usr/bin/env bash\ncd \"$(dirname \"$0\")\"\nexport PYTHONPATH=\"$PWD/kit\"\nexec \"%s\" -m homeai_setup.%s \"$@\"\n"
                  % (py, sub))
            os.chmod(p, 0o755)
            out[k] = p
        if "updater" in comps:
            out["model-updater"] = os.path.join(root, "extras", "model-updater", "run-model-updater.sh")
    return out


def _ps_quote(s):
    return "'" + s.replace("'", "''") + "'"


def make_shortcuts(root, scripts, log=say):
    """Returns the list of shortcut files created (the uninstaller offers to remove them)."""
    made = []
    icons = os.path.join(root, "kit", "icons")
    if IS_WIN:
        desktop = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
                               capture_output=True, text=True, timeout=30)
            if r.stdout.strip():
                desktop = r.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
        menu = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "HomeAI")
        os.makedirs(menu, exist_ok=True)
        lines = ["$s = New-Object -ComObject WScript.Shell"]
        for name, base, icon, _ in APPS + [("Uninstall HomeAI", "uninstall", "stop", None)]:
            if base not in scripts:
                continue
            targets = [os.path.join(menu, name + ".lnk")]
            if base in ("start-homeai", "stop-homeai"):
                targets.append(os.path.join(desktop, name + ".lnk"))
            for lnk in targets:
                lines += ["$l = $s.CreateShortcut(%s)" % _ps_quote(lnk),
                          "$l.TargetPath = %s" % _ps_quote(scripts[base]),
                          "$l.WorkingDirectory = %s" % _ps_quote(os.path.dirname(scripts[base])),
                          "$l.IconLocation = %s" % _ps_quote(os.path.join(icons, icon + ".ico") + ",0"),
                          "$l.WindowStyle = 7", "$l.Save()"]
                made.append(lnk)
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "\n".join(lines)],
                           capture_output=True, text=True, timeout=120)
        if r.returncode:
            log("   could not create shortcuts: " + (r.stderr or "")[-200:])
            return []
        made.append(menu)
    else:
        apps = os.path.join(os.path.expanduser("~"), ".local", "share", "applications")
        os.makedirs(apps, exist_ok=True)
        desk = os.path.join(os.path.expanduser("~"), "Desktop")
        for name, base, icon, _ in APPS:
            if base not in scripts:
                continue
            term = "false" if base in ("start-homeai", "stop-homeai") else "true"
            text = ("[Desktop Entry]\nType=Application\nName=%s\nExec=\"%s\"\nIcon=%s\nTerminal=%s\nCategories=Utility;\n"
                    % (name, scripts[base], os.path.join(icons, icon + ".png"), term))
            fn = "homeai-%s.desktop" % base
            for d in [apps] + ([desk] if base == "start-homeai" and os.path.isdir(desk) else []):
                p = os.path.join(d, fn)
                write(p, text)
                os.chmod(p, 0o755)
                made.append(p)
    log("   %d shortcut(s) created" % len(made))
    return made
