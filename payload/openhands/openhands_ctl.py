"""Start / stop OpenHands (Agent Canvas) in Docker, wired to HomeAI's local AI engine.

  python openhands_ctl.py start [--no-browser] | stop | status

The agent only sees extras/openhands/workspace. The UI listens on 127.0.0.1:3000 only. Analytics are switched off.
No account, no API key: the agent talks to the local AI engine (llama-server) through Docker's host gateway."""
import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "kit"))
IMAGE = "ghcr.io/openhands/agent-canvas:1.33.0"
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
           "max_input_tokens": max(4096, ctx - 8192), "max_output_tokens": min(16384, max(1024, ctx // 4)),
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


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"
    if cmd == "start":
        return start("--no-browser" not in sys.argv)
    if cmd == "stop":
        return stop()
    if cmd == "status":
        print("running" if http_ok(UI) else "stopped")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
