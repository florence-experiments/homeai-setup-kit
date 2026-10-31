"""Start, stop and check HomeAI: the AI engine (llama-server router), the HomeAI app, and SearXNG if installed.

  python -m homeai_setup.control start [--no-browser] | stop | status | start-engine

Everything listens on 127.0.0.1 only. Logs go to <HomeAI folder>/logs and are overwritten at each start."""
from __future__ import annotations

import json
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
    try:
        p = subprocess.Popen(cmd, **kw)
    finally:
        log.close()                                    # the child keeps its own copy of the handle
    write_pidfile(_pidfile(root, name), p.pid, cmd)
    return p


# ---- pid files: {"pid", "start", "cmd", "exe"}. A pid is only signalled when the running process is provably the
# one HomeAI started (same start time, same command line / program), so a stale or reused pid never kills anything.
def _proc_start(pid):
    """Process start time as an opaque token (Linux: clock ticks since boot; Windows: creation FILETIME), or None."""
    if IS_WIN:
        return (_win_proc(pid) or {}).get("start")
    try:
        with open("/proc/%d/stat" % pid, "rb") as f:
            stat = f.read().decode("utf-8", "replace")
        return int(stat[stat.rindex(")") + 2:].split()[19])      # field 22, counted after the "(comm)" field
    except (OSError, ValueError, IndexError):
        return None


def _proc_cmdline(pid):
    """Linux: argv of a running process as a list, or None."""
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            raw = f.read()
    except OSError:
        return None
    return [a.decode("utf-8", "surrogateescape") for a in raw.split(b"\0")[:-1]] if raw else None


def _win_proc(pid):
    """Windows: {'start': creation time, 'exe': full program path} of a running process, or None (stdlib ctypes)."""
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        h = k32.OpenProcess(0x1000, False, int(pid))            # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return None
        try:
            code = wintypes.DWORD()
            if not k32.GetExitCodeProcess(h, ctypes.byref(code)) or code.value != 259:     # 259 = STILL_ACTIVE
                return None
            ft = [wintypes.FILETIME() for _ in range(4)]
            if not k32.GetProcessTimes(h, *[ctypes.byref(x) for x in ft]):
                return None
            start = (ft[0].dwHighDateTime << 32) | ft[0].dwLowDateTime
            buf = ctypes.create_unicode_buffer(32768)
            n = wintypes.DWORD(len(buf))
            exe = buf.value if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else None
            return {"start": start, "exe": exe}
        finally:
            k32.CloseHandle(h)
    except (OSError, AttributeError, ValueError):
        return None


def _same_path(a, b):
    try:
        return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))
    except (TypeError, ValueError):
        return False


def write_pidfile(pf, pid, cmd):
    rec = {"pid": int(pid), "start": _proc_start(pid), "cmd": [str(c) for c in cmd],
           "exe": os.path.abspath(str(cmd[0]))}
    os.makedirs(os.path.dirname(pf), exist_ok=True)
    tmp = pf + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rec, f)
    os.replace(tmp, pf)


def read_pidfile(pf):
    """-> record dict or None. Old kits wrote a bare number: that gives {'pid': n} with nothing to check against."""
    try:
        with open(pf, encoding="utf-8") as f:
            raw = f.read().strip()
    except OSError:
        return None
    try:
        rec = json.loads(raw)
    except ValueError:
        rec = None
    if isinstance(rec, int):
        rec = {"pid": rec}
    if not isinstance(rec, dict):
        return None
    try:
        rec["pid"] = int(rec.get("pid"))
    except (TypeError, ValueError):
        return None
    return rec if rec["pid"] > 0 else None


def owned_pid(pf, expect_cmd=None):
    """The pid in pid file `pf` if that process is still the one HomeAI started, else None.
    expect_cmd: the command HomeAI would have started (used for old pid files that only hold a number)."""
    rec = read_pidfile(pf)
    if not rec:
        return None
    pid = rec["pid"]
    if pid == os.getpid():
        return None
    want = rec.get("cmd") or ([str(c) for c in expect_cmd] if expect_cmd else None)
    if not want:
        return None
    if rec.get("start") is not None and _proc_start(pid) != rec["start"]:
        return None                                    # pid gone or reused by a newer process
    if IS_WIN:
        info = _win_proc(pid)
        if not info or not info.get("exe") or not _same_path(info["exe"], rec.get("exe") or want[0]):
            return None
        return pid
    argv = _proc_cmdline(pid)
    if not argv:
        return None                                    # not running (or no /proc to check): never guess
    if argv == want or (len(argv) == len(want) and argv[1:] == want[1:] and _same_path(argv[0], want[0])):
        return pid
    return None


def kill_pidfile(pf, expect_cmd=None, log=None):
    """Stop the process recorded in pid file `pf` only if it is still ours; always removes the pid file.
    Returns True when a process was signalled."""
    if not os.path.exists(pf):
        return False
    pid = owned_pid(pf, expect_cmd)
    killed = False
    if pid is None:
        if log:
            log("%s: no matching HomeAI process is running (old pid file removed, nothing stopped)" % os.path.basename(pf))
    else:
        try:
            if IS_WIN:
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
            else:
                try:
                    own_group = os.getpgid(pid) == pid and pid != os.getpgrp()
                except OSError:
                    own_group = False
                if own_group:                          # started with start_new_session: the group is ours
                    os.killpg(pid, signal.SIGTERM)
                else:
                    os.kill(pid, signal.SIGTERM)
            killed = True
        except OSError:
            pass
    try:
        os.remove(pf)
    except OSError:
        pass
    return killed


def _kill(root, name, expect_cmd=None):
    return kill_pidfile(_pidfile(root, name), expect_cmd, say)


def app_cmd(root):
    app = os.path.join(root, "homeai")
    return [_python(root), os.path.join(app, "server.py")]


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
    _spawn(root, "homeai", app_cmd(root), app)
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
    _kill(root, "homeai", app_cmd(root))
    _kill(root, "engine", engine_cmd(root))
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
