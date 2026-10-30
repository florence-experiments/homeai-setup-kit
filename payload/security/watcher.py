# Built by Florence for the community.
"""Security Watcher for this PC (Phase 3).

Reads Sysmon (events 1, 3, 7, 8, 10, 22), the Security log (5152/5157 firewall blocks) and
pfirewall.log every ~2 s using incremental bookmarks, applies the rules in rules.py, closes
unapproved AI processes, shows a big on-top alert, logs to events.jsonl and serves the
Security Monitor page on http://127.0.0.1:8095.

Run:  pythonw.exe <HomeAI folder>\\extras\\security\\watcher.py            (normally started by the scheduled task)
      python.exe  <HomeAI folder>\\extras\\security\\watcher.py --no-gui   (console, no popups)
      python.exe  watcher.py --demo                    (mock data, any OS, for the dashboard)
Python standard library only.
"""
import argparse
import collections
import json
import ntpath
import os
import re
import binascii
import socket
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import dashboard   # noqa: E402
import enrich      # noqa: E402
import integrity   # noqa: E402
import parsers     # noqa: E402
import popup       # noqa: E402
import rules       # noqa: E402
import winutil     # noqa: E402
from actions import ActionsMixin        # noqa: E402
from closing import ClosingMixin        # noqa: E402
from demo import DemoMixin              # noqa: E402
from handlers import HandlersMixin      # noqa: E402
from selftest import SelfTestMixin      # noqa: E402
from state_view import StateMixin       # noqa: E402
from sources import EventLogTail, FirewallLogTail, JsonlLog, expand  # noqa: E402

VERSION = "1.0.0 (2026-10-29)"



# ----------------------------------------------------------------------------- engine
class Engine(HandlersMixin, ClosingMixin, ActionsMixin, SelfTestMixin, StateMixin, DemoMixin):
    def __init__(self, cfg_path, gui=True, demo=False):
        self.cfg_path = cfg_path
        self.cfg = self._load_cfg()
        self.demo = demo
        self.started = time.time()
        self.own_pid = os.getpid()
        self.parent_pid = os.getppid() if hasattr(os, "getppid") else 0
        p = self.cfg.get("paths", {})
        self.log_dir, self.state_dir = expand(p.get("log_dir")), expand(p.get("state_dir"))
        os.makedirs(self.state_dir, exist_ok=True)
        lg = self.cfg.get("logging", {})
        self.log = JsonlLog(os.path.join(self.log_dir, "events.jsonl"), lg.get("max_mb", 20), lg.get("keep_files", 3))
        self.port = int(self.cfg.get("dashboard", {}).get("port", 8095))
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.own_ips, self.gateways = self._detect_own_ips()
        self.rules = rules.Rules(self.cfg, self.own_pid, self.own_ips)
        self.page_key = binascii.hexlify(os.urandom(18)).decode()
        sc = self.cfg.get("port_scan", {})
        self.scan = parsers.ScanDetector(sc.get("distinct_ports", 10), sc.get("window_seconds", 60),
                                         sc.get("cooldown_seconds", 600))
        self.inbound = parsers.InboundStats()
        self.inbound_minute = collections.Counter()
        self.last_inbound_log = time.time()
        self.outbound_blocked = {}
        self.alerts = collections.deque(maxlen=300)
        self.alert_index = {}
        self.cooldown = {}
        self.expect_test_pids = {}
        self.dns_cache = collections.defaultdict(set)
        self.dns_order = collections.deque(maxlen=5000)
        self.kill_paused_until = 0
        self.counters = collections.Counter()
        self.geo = enrich.GeoDB(expand(p.get("geo_dir", "")))
        self.enricher = enrich.Enricher(self.cfg.get("enrichment", {}), self.geo, self.rules.trusted, self.dns_cache)
        ic = self.cfg.get("integrity", {})
        self.integrity = integrity.IntegrityMonitor(expand(ic.get("baseline_csv", "")), ic.get("files", []),
                                                    ic.get("check_seconds", 10))
        self.test_integrity = None
        src = self.cfg.get("sources", {})
        mpp, mbl = src.get("max_events_per_poll", 500), src.get("max_backlog_before_skip", 5000)
        self.sysmon = EventLogTail(src.get("sysmon_channel", "Microsoft-Windows-Sysmon/Operational"),
                                   src.get("sysmon_event_ids", [1, 3, 7, 8, 10, 22]), mpp, mbl)
        self.security = EventLogTail("Security", src.get("security_event_ids", [5152, 5157]), mpp, mbl)
        self.pfw = FirewallLogTail(expand(p.get("pfirewall_log", "")))
        self.popups = popup.PopupManager(self, enabled=gui and self.cfg.get("alerts", {}).get("popup", True))
        self.sysmon_service = None
        self.last_health = 0
        self.cpu_mark = (time.time(), time.process_time())
        self.cpu_pct = 0.0
        self.net_cache = {"at": 0, "rows": [], "procs": {}}
        self.images = {}
        self.dashboard_seen = 0
        self.loop_error = ""

    # ------------------------------------------------------------------ config
    def _load_cfg(self):
        with open(self.cfg_path, "r", encoding="utf-8-sig") as f:
            return json.load(f)

    def _save_cfg(self):
        tmp = self.cfg_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.cfg, f, indent=2)
        os.replace(tmp, self.cfg_path)

    def _detect_own_ips(self):
        ips = {"127.0.0.1", "::1"}
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None):
                ip = parsers.clean_ip(info[4][0])
                if ip:
                    ips.add(ip)
        except OSError:
            pass
        gws = []
        if winutil.IS_WIN:
            rc, out = winutil.run(["ipconfig"], timeout=10)
            text = parsers.decode_output(out)
            gws = parsers.parse_gateways(text)
            for m in re.finditer(r"IPv[46] Address[ .]*: ([0-9a-fA-F:.%]+)", text):
                ip = parsers.clean_ip(m.group(1))
                if ip:
                    ips.add(ip)
        return ips, gws

    def note(self, msg, **kw):
        self.log.write("note", message=msg, **kw)

    # ------------------------------------------------------------------ main loop
    def loop(self):
        poll = max(1.0, float(self.cfg.get("poll_seconds", 2)))
        self.log.write("start", version=VERSION, pid=self.own_pid, admin=winutil.is_admin(),
                       own_ips=sorted(self.own_ips), gateways=self.gateways)
        if self.cfg.get("enrichment", {}).get("offline_geo", True):
            threading.Thread(target=self._load_geo, name="geo-load", daemon=True).start()
        while not self.stop_event.is_set():
            t0 = time.time()
            try:
                self.tick()
                self.loop_error = ""
            except Exception as e:      # keep running whatever happens
                self.loop_error = "%s: %s" % (type(e).__name__, e)
                self.log.write("error", where="loop", error=self.loop_error)
            self.stop_event.wait(max(0.2, poll - (time.time() - t0)))
        self.log.write("stop", pid=self.own_pid)

    def _load_geo(self):
        self.geo.load()
        self.log.write("geo", loaded=self.geo.loaded, files=self.geo.files, error=self.geo.error)

    def tick(self):
        src = self.cfg.get("sources", {})
        if src.get("sysmon", True):
            for ev in self.sysmon.poll():
                self.on_sysmon(ev)
        pf_ok = False
        if src.get("pfirewall", True):
            for rec in self.pfw.poll():
                self.on_pfirewall(rec)
            pf_ok = self.pfw.state == "ok"
        if src.get("security_log", True):
            use_inbound = src.get("inbound_from_security_log", "auto")
            inbound_too = use_inbound is True or (use_inbound == "auto" and not pf_ok)
            for ev in self.security.poll():
                self.on_wfp(ev, inbound_too)
        if self.cfg.get("integrity", {}).get("enabled", True):
            for st in self.integrity.check():
                self.on_tamper(st)
        now = time.time()
        if now - self.last_health > 30:
            self.last_health = now
            if winutil.IS_WIN:
                self.sysmon_service = winutil.service_running("Sysmon64") or winutil.service_running("Sysmon")
            for pid, until in list(self.expect_test_pids.items()):
                if until < now:
                    self.expect_test_pids.pop(pid, None)
        every = self.cfg.get("logging", {}).get("log_inbound_summary_seconds", 60)
        if now - self.last_inbound_log >= every:
            if self.inbound_minute:
                self.log.write("inbound_summary", seconds=round(now - self.last_inbound_log),
                               blocked_by_ip=dict(self.inbound_minute.most_common(50)))
            self.inbound_minute.clear()
            self.last_inbound_log = now



# ----------------------------------------------------------------------------- command line
def make_baseline(cfg_path):
    """Writes baseline-hashes.csv from the files as they are now, and creates missing .good copies."""
    import shutil
    with open(cfg_path, "r", encoding="utf-8-sig") as f:
        cfg = json.load(f)
    ic = cfg.get("integrity", {})
    rows = []
    for item in ic.get("files", []):
        p = item["path"]
        if not os.path.exists(p):
            print("MISSING (skipped):", p)
            continue
        rows.append({"Algorithm": "SHA256", "Hash": integrity.sha256_file(p), "Path": p})
        good = item.get("good")
        if good and not os.path.exists(good):
            shutil.copy2(p, good)
            print("created good copy:", good)
        print("hashed:", p)
    if not rows:
        print("No files found - baseline not written.")
        return 1
    os.makedirs(os.path.dirname(ic["baseline_csv"]), exist_ok=True)
    integrity.write_baseline(ic["baseline_csv"], rows, True)
    print("Baseline written:", ic["baseline_csv"])
    return 0


def demo_config(cfg_path):
    import tempfile
    with open(cfg_path, "r", encoding="utf-8-sig") as f:
        cfg = json.load(f)
    base = os.path.join(tempfile.gettempdir(), "security-watcher-demo")
    cfg["paths"].update(log_dir=os.path.join(base, "logs"), state_dir=os.path.join(base, "state"),
                        geo_dir=os.path.join(base, "geo"), pfirewall_log=os.path.join(base, "pfirewall.log"))
    cfg["sources"].update(sysmon=False, security_log=False, pfirewall=False)
    cfg["enrichment"].update(reverse_dns=False, traceroute=False, online_geo=False)
    os.makedirs(base, exist_ok=True)
    path = os.path.join(base, "config.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Security Watcher (Phase 3)")
    ap.add_argument("--config", default=os.path.join(HERE, "config.json"))
    ap.add_argument("--no-gui", action="store_true", help="no popups (console use)")
    ap.add_argument("--demo", action="store_true", help="made-up data, to preview the Monitor page")
    ap.add_argument("--make-baseline", action="store_true", help="hash the protected files now and exit")
    ap.add_argument("--port", type=int, default=0)
    args = ap.parse_args(argv)
    if args.make_baseline:
        return make_baseline(args.config)
    cfg_path = demo_config(args.config) if args.demo else args.config
    eng = Engine(cfg_path, gui=not args.no_gui and not args.demo, demo=args.demo)
    eng.version = VERSION
    if args.port:
        eng.port = args.port
    host = eng.cfg.get("dashboard", {}).get("host", "127.0.0.1")
    try:
        srv = dashboard.start(eng, host, eng.port, eng.page_key)
    except OSError:
        msg = "Security Watcher is already running (port %d is in use)." % eng.port
        print(msg)
        eng.log.write("note", message=msg)
        return 2
    with open(os.path.join(eng.state_dir, "watcher.pid"), "w") as f:
        f.write(str(eng.own_pid))
    print("Security Watcher %s - Monitor: http://127.0.0.1:%d/" % (VERSION, eng.port))
    if args.demo:
        eng.demo_seed()
    else:
        threading.Thread(target=eng.loop, name="watch-loop", daemon=True).start()
    try:
        eng.popups.run_forever(eng.stop_event)
    except KeyboardInterrupt:
        eng.stop_event.set()
    srv.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
