"""Start, stop and check HomeAI: the AI engine (llama-server router), the HomeAI app, and SearXNG if installed.

  python -m homeai_setup.control start [--no-browser] | stop | status | start-engine

Everything listens on 127.0.0.1 only. Logs go to <HomeAI folder>/logs and are overwritten at each start."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser

from .util import IS_WIN, KIT_DIR, read_json

ROOT = os.path.dirname(KIT_DIR)
ENGINE_PORT = 8081
APP_PORT = 8090


def say(m):
    print("[HomeAI] " + m, flush=True)


def ok(url, timeout=2):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _state(root):
    return read_json(os.path.join(root, "install.json"), {}) or {}


def _python(root):
    p = os.path.join(root, "python", "python.exe")
    return p if IS_WIN and os.path.isfile(p) else (_state(root).get("python") or sys.executable)


def _pidfile(root, name):
    d = os.path.join(root, "run")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, name + ".pid")


def _spawn(root, name, cmd, cwd):
    logs = os.path.join(root, "logs")
    os.makedirs(logs, exist_ok=True)
    log = open(os.path.join(logs, name + ".log"), "w", encoding="utf-8")
    kw = {"cwd": cwd, "stdin": subprocess.DEVNULL, "stdout": log, "stderr": subprocess.STDOUT}
    if IS_WIN:
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    p = subprocess.Popen(cmd, **kw)
    with open(_pidfile(root, name), "w") as f:
        f.write(str(p.pid))
    return p


def _kill(root, name):
    pf = _pidfile(root, name)
    try:
        with open(pf) as f:
            pid = int(f.read().strip())
    except (OSError, ValueError):
        return False
    try:
        if IS_WIN:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        else:
            try:
                os.killpg(pid, signal.SIGTERM)
            except OSError:
                os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
    try:
        os.remove(pf)
    except OSError:
        pass
    return True


def engine_cmd(root):
    exe = os.path.join(root, "engine", "llama.cpp", "llama-server.exe" if IS_WIN else "llama-server")
    return [exe, "--models-preset", os.path.join(root, "engine", "models.ini"), "--models-max", "1",
            "--host", "127.0.0.1", "--port", str(ENGINE_PORT)]


def start_engine(root=ROOT, wait=60):
    if ok("http://127.0.0.1:%d/health" % ENGINE_PORT):
        return True
    cmd = engine_cmd(root)
    if not os.path.isfile(cmd[0]):
        say("AI engine not found at %s - run setup again." % cmd[0])
        return False
    say("Starting the AI engine...")
    _spawn(root, "engine", cmd, os.path.dirname(cmd[0]))
    end = time.time() + wait
    while time.time() < end:
        if ok("http://127.0.0.1:%d/health" % ENGINE_PORT):
            return True
        time.sleep(1)
    say("The AI engine did not answer yet - see logs/engine.log")
    return False


def start_app(root=ROOT, wait=30):
    if ok("http://127.0.0.1:%d/" % APP_PORT):
        return True
    say("Starting HomeAI...")
    app = os.path.join(root, "homeai")
    _spawn(root, "homeai", [_python(root), os.path.join(app, "server.py")], app)
    end = time.time() + wait
    while time.time() < end:
        if ok("http://127.0.0.1:%d/" % APP_PORT):
            return True
        time.sleep(1)
    say("HomeAI did not answer yet - see logs/homeai.log")
    return False


def _compose(root, *args):
    f = os.path.join(root, "extras", "searxng", "compose.yaml")
    if not os.path.isfile(f):
        return None
    try:
        return subprocess.run(["docker", "compose", "-f", f] + list(args), capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError):
        return None


def start(root=ROOT, browser=True):
    if (_state(root).get("components") or {}).get("searxng"):
        r = _compose(root, "up", "-d")
        if r is None or r.returncode:
            say("Web search (SearXNG) not started: is Docker running? HomeAI works without it.")
    e = start_engine(root)
    a = start_app(root)
    if a:
        say("Ready: http://127.0.0.1:%d/" % APP_PORT)
        if browser:
            webbrowser.open("http://127.0.0.1:%d/" % APP_PORT)
    return 0 if (e and a) else 1


def stop(root=ROOT):
    _kill(root, "homeai")
    _kill(root, "engine")
    if (_state(root).get("components") or {}).get("searxng"):
        _compose(root, "stop")
    oh = os.path.join(root, "extras", "openhands", "openhands_ctl.py")
    if os.path.isfile(oh):
        subprocess.run([_python(root), oh, "stop"], capture_output=True)
    say("Stopped.")
    return 0


def status(root=ROOT):
    say("AI engine : %s" % ("running" if ok("http://127.0.0.1:%d/health" % ENGINE_PORT) else "stopped"))
    say("HomeAI    : %s" % ("running" if ok("http://127.0.0.1:%d/" % APP_PORT) else "stopped"))
    return 0


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    cmd = a[0] if a else "start"
    if cmd == "start":
        return start(browser="--no-browser" not in a)
    if cmd == "stop":
        return stop()
    if cmd == "status":
        return status()
    if cmd == "start-engine":
        return 0 if start_engine() else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
