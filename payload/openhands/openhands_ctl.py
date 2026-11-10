"""Start / stop OpenHands (Agent Canvas) in Docker, wired to HomeAI's local AI engine.

  python openhands_ctl.py start [--no-browser] | stop | stop-task | status

The agent only sees extras/openhands/workspace. The UI listens on 127.0.0.1:3000 only. Analytics are switched off.
No account, no API key: the agent talks to the local AI engine (llama-server) through Docker's host gateway."""
import json
import re
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "kit"))
IMAGE = "ghcr.io/openhands/agent-canvas:1.38.0"
NAME = "homeai-openhands"
UI = "http://127.0.0.1:3000/canvas"
API = "http://127.0.0.1:3000"
IS_WIN = os.name == "nt"
PIDFILE = os.path.join(HERE, "state", "bridge.pid")


def say(m):
    print("[OpenHands] " + m, flush=True)


def http_ok(u, timeout=3):
    try:
        with urllib.request.urlopen(u, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def docker(*a, check=False):
    return subprocess.run(["docker"] + list(a), capture_output=True, text=True, check=check)


def docker_up(wait=180):
    if docker("info").returncode == 0:
        return True
    if IS_WIN:
        exe = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Docker", "Docker", "Docker Desktop.exe")
        if os.path.isfile(exe):
            say("Starting Docker Desktop...")
            subprocess.Popen([exe], close_fds=True)
    else:
        say("Docker is not running. Start it with: sudo systemctl start docker")
    end = time.time() + wait
    while time.time() < end:
        time.sleep(3)
        if docker("info").returncode == 0:
            return True
    return False


def engine_up():
    if http_ok("http://127.0.0.1:8081/health"):
        return True
    from homeai_setup import control
    control.start_engine(ROOT)
    end = time.time() + 180
    while time.time() < end:
        if http_ok("http://127.0.0.1:8081/health"):
            return True
        time.sleep(2)
    return False


def bridge_ip():
    r = docker("network", "inspect", "bridge", "-f", "{{range .IPAM.Config}}{{.Gateway}}{{end}}")
    ip = (r.stdout or "").strip()
    return ip or "172.17.0.1"


def _bridge_cmd():
    return [sys.executable, os.path.join(HERE, "bridge.py"), bridge_ip(), "8081"]


def start_bridge():
    """Linux: forward <docker gateway>:8081 -> 127.0.0.1:8081 so the container can reach the engine."""
    if IS_WIN:
        return
    from homeai_setup import control
    cmd = _bridge_cmd()
    if control.owned_pid(PIDFILE, cmd):
        return                                    # our bridge is still running
    os.makedirs(os.path.dirname(PIDFILE), exist_ok=True)
    p = subprocess.Popen(cmd, start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    control.write_pidfile(PIDFILE, p.pid, cmd)


def stop_bridge():
    """Stops the bridge only if the pid file still points at it (a stale or reused pid is left alone)."""
    if not os.path.exists(PIDFILE):
        return
    from homeai_setup import control
    control.kill_pidfile(PIDFILE, _bridge_cmd())


def container_state():
    r = docker("inspect", "-f", "{{.State.Running}}", NAME)
    return None if r.returncode else r.stdout.strip()


def run_container():
    st = container_state()
    if st == "true":
        say("Already running.")
        return
    if st == "false":
        say("Starting the existing container...")
        docker("start", NAME, check=True)
        return
    ws, state = os.path.join(HERE, "workspace"), os.path.join(HERE, "state")
    for d in (ws, state):
        os.makedirs(d, exist_ok=True)
    say("Creating the container (the first start downloads the image, a few GB)...")
    args = ["run", "-d", "--name", NAME, "-p", "127.0.0.1:3000:8000",
            "-e", "AGENT_CANVAS_ALLOW_LAN_SESSION_KEY=true", "-e", "DO_NOT_TRACK=1", "-e", "VITE_DO_NOT_TRACK=1",
            "-v", state + ":/home/openhands/.openhands",
            "-v", ws + ":/home/openhands/workspace", "-v", ws + ":/projects", "-v", ws + ":/workspace"]
    if not IS_WIN:
        args += ["--add-host", "host.docker.internal:host-gateway"]
    docker(*(args + [IMAGE]), check=True)


def req(method, path, key, body=None):
    data = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(API + path, data=data, method=method,
                               headers={"X-Session-API-Key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=30) as f:
        return json.loads(f.read() or b"null")


def configure():
    from homeai_setup import configgen
    st = configgen.load_state(ROOT) or {}
    mm = (st.get("modes") or {}).get("coding") or (st.get("modes") or {}).get("general")
    if not mm:
        say("No HomeAI model found to use - add the Coding mode first.")
        return
    sec = mm["section"]
    ctx = int((st.get("models", {}).get(sec) or {}).get("ctx") or 32768)
    kf = os.path.join(HERE, "state", "agent-canvas", "api-key.txt")
    end = time.time() + 60
    while not os.path.isfile(kf) and time.time() < end:
        time.sleep(2)
    if not os.path.isfile(kf):
        say("Could not find the OpenHands session key; set the model in its settings page instead: openai/" + sec)
        return
    with open(kf, encoding="utf-8") as f:
        key = f.read().strip()
    llm = {"model": "openai/" + sec, "base_url": "http://host.docker.internal:8081/v1", "api_key": "sk-local-no-key",
           "api_mode": "chat", "timeout": 900, "stream_idle_timeout": 600, "num_retries": 3,
           "max_input_tokens": max(4096, ctx - 8192), "max_output_tokens": min(16384, max(1024, ctx // 2)),
           "temperature": 0.6, "caching_prompt": False, "native_tool_calling": True,
           "capability_overrides": {"supports_responses_api": False, "supports_prompt_cache": False,
                                    "supports_reasoning_effort": False}}
    try:
        req("POST", "/api/profiles/homeai-local", key, {"llm": llm, "include_secrets": True})
        req("POST", "/api/profiles/homeai-local/activate", key)
        req("PATCH", "/api/settings", key, {
            "agent_settings_diff": {"llm": llm, "condenser": {"enabled": True, "max_tokens": max(4096, int(ctx * 0.7))}},
            "conversation_settings_diff": {"confirmation_mode": False, "max_iterations": 150},
            "misc_settings_diff": {"app_preferences": {"user_consents_to_analytics": False}}})
        say("Configured to use the local model %s." % sec)
    except Exception as e:  # noqa
        say("Could not configure OpenHands automatically (%s). In its settings choose model openai/%s, base URL "
            "http://host.docker.internal:8081/v1, API key sk-local-no-key." % (e, sec))


def start(browser=True):
    if not docker_up():
        say("Docker is not available. Install Docker Desktop (Windows) or Docker Engine (Linux) first.")
        return 1
    if not engine_up():
        say("The AI engine did not start. Start HomeAI first.")
        return 1
    start_bridge()
    run_container()
    end = time.time() + 300
    while not http_ok(UI) and time.time() < end:
        time.sleep(2)
    if not http_ok(UI):
        say("OpenHands did not answer at %s yet. Check Docker Desktop." % UI)
        return 1
    configure()
    say("Ready: " + UI)
    if browser:
        webbrowser.open(UI)
    return 0


def stop():
    if container_state() == "true":
        docker("stop", NAME)
    stop_bridge()
    say("Stopped.")
    return 0


def _session_key():
    kf = os.path.join(HERE, "state", "agent-canvas", "api-key.txt")
    if not os.path.isfile(kf):
        return None
    with open(kf, encoding="utf-8") as f:
        return f.read().strip() or None


def _conversations(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in ("conversations", "items", "results", "data"):
            v = data.get(k)
            if isinstance(v, list):
                return v
    return []


def _is_active(status):
    s = str(status or "").strip().lower().replace("-", "_")
    return s in ("running", "stuck", "executing", "in_progress", "busy", "working", "awaiting_agent")


def _cx(*cmd):
    """docker exec into the OpenHands container; never throws on a non-zero exit."""
    r = docker("exec", NAME, *cmd)
    return r.returncode, (r.stdout or ""), (r.stderr or "")


def _is_service_cmd(args):
    a = args or ""
    return bool(
        re.search(r"(^|/)tini(\s|$)", a)
        or "agent-canvas/entrypoint.sh" in a
        or re.search(r"(^|/)openhands-agent-server(\s|$)", a)
        or "openhands.automation.app" in a
        or "agent-canvas/static-server.mjs" in a
        or "openhands-code-server" in a
        or "/openhands/.code-server" in a
        or "code_server_proxy" in a
        or re.search(r"(^|\s)ps\s+-eo\s", a)
    )


def _is_keep_cmd(args):
    return bool(re.search(r"(^|/)(tmux|screen)(\s|$)", args or ""))


def _is_idle_shell(args):
    parts = (args or "").split()
    if not parts:
        return False
    name = os.path.basename(parts[0].strip('"'))
    if name not in ("bash", "sh", "dash", "ash", "zsh", "fish"):
        return False
    if re.search(r"\s-c\s|\s-lc\s", args):
        return False
    return all(p.startswith("-") for p in parts[1:])


def _cx_ps():
    code, out, err = _cx("sh", "-c", "ps -eo pid,ppid,etime,args")
    if code != 0:
        raise RuntimeError((err or out).strip() or "ps failed")
    rows = []
    for line in out.splitlines():
        m = re.match(r"\s*(\d+)\s+(\d+)\s+(\S+)\s+(.*)$", line)
        if not m:
            continue
        rows.append({"pid": int(m.group(1)), "ppid": int(m.group(2)),
                     "etime": m.group(3), "args": m.group(4).strip()})
    return rows


def _children(root, by_parent):
    out, stack, seen = [], [root], set()
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        for child in by_parent.get(cur, []):
            out.append(child)
            stack.append(child)
    return out


def _tmux_pane_pids():
    code, out, _ = _cx("sh", "-c", 'find /tmp -type s -path "*/tmux-*/*"')
    if code != 0:
        return []
    pids = []
    for sock in out.splitlines():
        sock = sock.strip()
        if not re.match(r"^/tmp/\S+$", sock):
            continue
        c, panes, _ = _cx("sh", "-c", "tmux -S '%s' list-panes -a -F '#{pane_pid}'" % sock)
        if c != 0:
            continue
        for p in panes.splitlines():
            if p.strip().isdigit() and int(p.strip()) > 1:
                pids.append(int(p.strip()))
    return pids


def kill_leftover_agent_processes():
    """End leftover agent tool processes inside the container; leave servers running."""
    if container_state() != "true":
        return 0
    say("Checking for leftover agent processes...")
    try:
        procs = _cx_ps()
    except Exception as e:  # noqa
        say("Could not inspect the container (%s)." % e)
        return 0
    by_pid = {r["pid"]: r for r in procs}
    by_parent = {}
    for r in procs:
        by_parent.setdefault(r["ppid"], []).append(r["pid"])
    protected = {1}
    for r in procs:
        if r["pid"] == 1 or _is_service_cmd(r["args"]):
            protected.add(r["pid"])
    tini_ids = [r["pid"] for r in procs if re.search(r"(^|/)tini(\s|$)", r["args"])]
    kill = []

    def add(pid):
        if pid <= 1 or pid in protected or pid not in by_pid:
            return
        if _is_keep_cmd(by_pid[pid]["args"]):
            return
        if by_pid[pid]["ppid"] in protected:
            return
        if pid not in kill:
            kill.append(pid)

    for pane in _tmux_pane_pids():
        if pane not in by_pid or pane in protected:
            continue
        kids = _children(pane, by_parent)
        if _is_idle_shell(by_pid[pane]["args"]):
            for k in kids:
                add(k)
        else:
            add(pane)
            for k in kids:
                add(k)
    for r in procs:
        if _is_keep_cmd(r["args"]):
            continue
        if r["ppid"] != 1 and r["ppid"] not in tini_ids:
            continue
        if r["pid"] in protected or _is_service_cmd(r["args"]):
            continue
        add(r["pid"])
        for k in _children(r["pid"], by_parent):
            add(k)
    if not kill:
        say("No leftover agent processes.")
        return 0
    # leaves first
    kill.sort(key=lambda pid: (len(_children(pid, by_parent)), -pid))
    say("Stopping %d leftover process%s:" % (len(kill), "" if len(kill) == 1 else "es"))
    for pid in kill:
        say("  PID %s  %s" % (pid, by_pid[pid]["args"]))
    ids = " ".join(str(pid) for pid in kill)
    _cx("sh", "-c", "kill -TERM %s" % ids)
    time.sleep(1)
    still = []
    for pid in kill:
        c, _, _ = _cx("sh", "-c", "kill -0 %s" % pid)
        if c == 0:
            still.append(pid)
    if still:
        _cx("sh", "-c", "kill -KILL %s" % " ".join(str(pid) for pid in still))
        time.sleep(0.4)
    ended = failed = 0
    for pid in kill:
        c, _, _ = _cx("sh", "-c", "kill -0 %s" % pid)
        if c != 0:
            say("Ended PID %s  %s" % (pid, by_pid[pid]["args"]))
            ended += 1
        else:
            say("Still running PID %s  %s" % (pid, by_pid[pid]["args"]))
            failed += 1
    if failed:
        say("Ended %d, still running %d." % (ended, failed))
    else:
        say("Ended %d leftover process%s." % (ended, "" if ended == 1 else "es"))
    return failed


def stop_task():
    """Interrupt running or stuck conversations and end leftover agent processes.

    Leaves the container and the AI engine running."""
    rc = 0
    container_up = container_state() == "true"
    if not http_ok(API):
        say("OpenHands is not running.")
        if container_up:
            if kill_leftover_agent_processes():
                rc = 1
        return 1
    key = _session_key()
    if not key:
        say("Could not find the OpenHands session key; open the UI and stop the task from there.")
        if container_up:
            if kill_leftover_agent_processes():
                rc = 1
        return 1
    try:
        data = req("GET", "/api/conversations/search", key)
    except Exception as e:  # noqa
        say("Could not list conversations (%s)." % e)
        if container_up and kill_leftover_agent_processes():
            return 1
        return 1
    active = []
    for c in _conversations(data):
        if not isinstance(c, dict):
            continue
        if _is_active(c.get("execution_status") or c.get("status")):
            cid = c.get("id") or c.get("conversation_id")
            if cid:
                active.append(str(cid))
    if not active:
        say("No running OpenHands task.")
    else:
        n = 0
        for cid in active:
            try:
                req("POST", "/api/conversations/%s/interrupt" % cid, key)
                n += 1
                say("Interrupted conversation %s." % cid)
            except Exception as e:  # noqa
                say("Could not interrupt %s (%s)." % (cid, e))
        if not n:
            rc = 1
    if container_up and kill_leftover_agent_processes():
        rc = 1
    say("The container and the AI engine were left running.")
    return rc


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"
    if cmd == "start":
        return start("--no-browser" not in sys.argv)
    if cmd == "stop":
        return stop()
    if cmd in ("stop-task", "interrupt"):
        return stop_task()
    if cmd == "status":
        print("running" if http_ok(UI) else "stopped")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
