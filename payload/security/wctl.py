"""Small helper for the .cmd files: status, stop, safe self-test, and baseline.

  python wctl.py status | stop | test | baseline [--refresh-good]
Standard library only. Talks to the watcher on 127.0.0.1 (never the internet), except for the
self-test's dummy process, which tries to reach 1.1.1.1:443 on purpose so the watcher catches it."""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def load_cfg():
    with open(os.path.join(HERE, "config.json"), "r", encoding="utf-8-sig") as f:
        return json.load(f)


def base_url():
    return "http://127.0.0.1:%d" % int(load_cfg().get("dashboard", {}).get("port", 8095))


def page_key():
    with urllib.request.urlopen(base_url() + "/", timeout=5) as r:
        m = re.search(r'TOKEN="([0-9a-f]+)"', r.read().decode("utf-8", "replace"))
    return m.group(1) if m else ""


def post(path, body, key):
    req = urllib.request.Request(base_url() + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Token": key})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return json.loads(e.read() or b"{}")


def get_state(key):
    req = urllib.request.Request(base_url() + "/api/state", headers={"X-Token": key})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def running():
    try:
        with urllib.request.urlopen(base_url() + "/health", timeout=3) as r:
            return r.status == 200
    except OSError:
        return False
import urllib.error  # noqa: E402

DUMMY = r"""
import socket, time
end = time.time() + 90
while time.time() < end:
    try:
        s = socket.create_connection(("1.1.1.1", 443), timeout=5)
        time.sleep(3)
        s.close()
    except OSError:
        time.sleep(2)
"""


def alive(p):
    return p.poll() is None


def wait_dead(p, seconds):
    end = time.time() + seconds
    while time.time() < end:
        if not alive(p):
            return True
        time.sleep(0.5)
    return False


def cmd_test():
    print("Security Watcher self-test (safe: nothing real is changed)\n")
    if not running():
        print("FAIL  The watcher is not running. Start it with Start-Watcher.cmd first.")
        return 1
    key = page_key()
    results = []

    r = post("/api/test", {"kind": "scan"}, key)
    results.append(("Port-scan detection (fake firewall lines)", r.get("ok"), r.get("message")))

    r = post("/api/test", {"kind": "tamper"}, key)
    results.append(("File-change detection (temp copy)", r.get("ok"), r.get("message")))

    py = os.path.join(os.path.dirname(sys.executable), "python.exe") if sys.platform == "win32" else sys.executable
    print("Starting a dummy python.exe that tries to reach 1.1.1.1:443 ...")
    p = subprocess.Popen([py, "-c", DUMMY], creationflags=CREATE_NO_WINDOW)
    post("/api/test", {"kind": "expect_pid", "pid": p.pid}, key)
    if wait_dead(p, 25):
        results.append(("AI-app internet block (real Sysmon / firewall path)", True,
                        "dummy pid %d was closed by the watcher" % p.pid))
    else:
        print("  not caught by the real path within 25 s - trying the synthetic event ...")
        r = post("/api/test", {"kind": "outbound", "pid": p.pid}, key)
        ok = bool(r.get("ok")) and wait_dead(p, 10)
        results.append(("AI-app internet block (synthetic event - real path did NOT fire)", ok,
                        r.get("message", "")))
        results.append(("Real Sysmon path", False, "check Sysmon is running and config.json ai_processes"))
    if alive(p):
        p.kill()

    print()
    for name, ok, msg in results:
        print("%s  %s\n      %s" % ("PASS" if ok else "FAIL", name, msg or ""))
    print("\nExpect TEST popups on screen. Click Dismiss, or try Restore file on the file alert.")
    print("Monitor page: %s/" % base_url())
    return 0 if all(ok for _, ok, _ in results) else 1


def cmd_status():
    if not running():
        print("Security Watcher: NOT running")
        return 1
    s = get_state(page_key())
    print("Security Watcher: running -", s["status"]["text"])
    print("  " + s["kill"]["text"])
    for k, v in s["health"].items():
        if isinstance(v, dict) and "state" in v:
            print("  %-10s %-5s %s" % (k, v["state"], v.get("msg", "")))
    print("  Monitor page: %s/" % base_url())
    return 0


def cmd_stop():
    if not running():
        print("Security Watcher is not running.")
        return 0
    r = post("/api/action", {"action": "shutdown"}, page_key())
    print(r.get("message", r))
    for _ in range(20):
        if not running():
            print("Stopped.")
            return 0
        time.sleep(0.5)
    print("Still running - use Task Manager or: schtasks /End /TN \"Security Watcher\"")
    return 1


def cmd_baseline(refresh_good):
    import integrity
    ic = load_cfg().get("integrity", {})
    rows = []
    for item in ic.get("files", []):
        p, good = item["path"], item.get("good")
        if not os.path.exists(p):
            print("MISSING (skipped):", p)
            continue
        rows.append({"Algorithm": "SHA256", "Hash": integrity.sha256_file(p), "Path": p})
        if good and (refresh_good or not os.path.exists(good)):
            if os.path.exists(good):
                shutil.copy2(good, good + ".bak-" + time.strftime("%Y%m%d-%H%M%S"))
            shutil.copy2(p, good)
            print("good copy saved:", good)
        print("hashed:", p)
    if not rows:
        print("No protected files found - nothing written.")
        return 1
    os.makedirs(os.path.dirname(ic["baseline_csv"]), exist_ok=True)
    integrity.write_baseline(ic["baseline_csv"], rows, True)
    print("Baseline written:", ic["baseline_csv"])
    return 0


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "test":
        return cmd_test()
    if cmd == "stop":
        return cmd_stop()
    if cmd == "baseline":
        return cmd_baseline("--refresh-good" in argv)
    return cmd_status()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
