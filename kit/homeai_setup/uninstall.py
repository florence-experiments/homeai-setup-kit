"""Uninstall HomeAI. Asks before EVERY delete (type yes); anything you don't confirm is left exactly as it is."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

from . import control
from .util import IS_WIN, KIT_DIR, Asker, is_yes, read_json, say

ROOT = os.path.dirname(KIT_DIR)


def _size_gb(path):
    tot = 0
    for d, _, files in os.walk(path):
        for f in files:
            try:
                tot += os.path.getsize(os.path.join(d, f))
            except OSError:
                pass
    return tot / 1e9


def _rm(path):
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    elif os.path.exists(path):
        os.remove(path)


def main(argv=None, ask=None):
    root = ROOT
    ask = ask or Asker()
    st = read_json(os.path.join(root, "install.json"), None)
    if not st:
        say("No HomeAI installation found in %s" % root)
        return 2
    say("HomeAI uninstaller - each item is only deleted if you type yes.\n")
    control.stop(root)

    def offer(key, question, action):
        if is_yes(ask.ask(key, question + " Type yes to delete: ", "")):
            action()
            say("   deleted")
        else:
            say("   kept")

    sc = [p for p in st.get("shortcuts", []) if os.path.exists(p)]
    if sc:
        offer("shortcuts", "Remove %d HomeAI shortcut(s) from the desktop / menu?" % len(sc), lambda: [_rm(p) for p in sc])
    comps = st.get("components") or {}
    if comps.get("openhands"):
        offer("openhands", "Remove the OpenHands Docker container and its image?", lambda: (
            subprocess.run(["docker", "rm", "-f", "homeai-openhands"], capture_output=True),
            subprocess.run(["docker", "rmi", "ghcr.io/openhands/agent-canvas:1.33.0"], capture_output=True)))
    if comps.get("searxng"):
        f = os.path.join(root, "extras", "searxng", "compose.yaml")
        offer("searxng", "Remove the SearXNG Docker container, its cache and its image?", lambda: subprocess.run(
            ["docker", "compose", "-f", f, "down", "-v", "--rmi", "all"], capture_output=True))
    if comps.get("security") and IS_WIN:
        say("Security Monitor: to remove its logon task and Sysmon, run (as administrator) "
            "extras\\security\\Uninstall-Watcher-Task.cmd and Uninstall-Sysmon.cmd BEFORE deleting the folder.")
        if not is_yes(ask.ask("security_done", "Type yes when done (or to continue anyway): ", "")):
            say("Stopped - nothing else was changed.")
            return 1
    for key, rel, what in (("models", "models", "all downloaded AI models"),
                           ("chats", os.path.join("homeai", "data"), "your chats, presets and settings"),
                           ("openhands_ws", os.path.join("extras", "openhands", "workspace"), "the OpenHands workspace (files the agent made)")):
        p = os.path.join(root, rel)
        if os.path.isdir(p):
            offer(key, "Delete %s (%s, %.1f GB)?" % (what, p, _size_gb(p)), lambda p=p: _rm(p))
    left = [n for n in os.listdir(root)]
    if left:
        offer("rest", "Delete the rest of the HomeAI folder (%s: the app, AI engine, Python, extras, logs)?" % root,
              lambda: _rm_rest(root))
    say("\nUninstall finished. Anything you kept is still in %s" % root)
    return 0


def _rm_rest(root):
    keep = {"models"} if os.path.isdir(os.path.join(root, "models")) else set()
    data = os.path.join(root, "homeai", "data")
    for name in os.listdir(root):
        p = os.path.join(root, name)
        if name in keep or name in ("kit", "python"):
            continue
        if name == "homeai" and os.path.isdir(data):        # chats were kept on purpose
            for n in os.listdir(p):
                if n != "data":
                    _rm(os.path.join(p, n))
            continue
        _rm(p)
    if IS_WIN:
        # this script runs from kit\ and python\, so those are removed by a short helper after it exits
        cmd = 'ping -n 3 127.0.0.1 >nul & rmdir /s /q "%s" & rmdir /s /q "%s" & rmdir "%s"' % (
            os.path.join(root, "kit"), os.path.join(root, "python"), root)
        subprocess.Popen(["cmd", "/c", cmd], creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True, cwd=os.path.dirname(root))
    else:
        _rm(os.path.join(root, "kit"))
        try:
            os.rmdir(root)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
