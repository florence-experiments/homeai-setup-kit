"""--demo mode: fills the engine with made-up data so the Monitor page can be previewed on any OS.
Nothing here runs during normal monitoring."""
import os
import time

import integrity

DEMO_PROCS = {1200: (900, "python.exe"), 1300: (900, "llama-server.exe"), 1400: (900, "Grok Bot.exe"),
              1500: (900, "chrome.exe"), 1600: (900, "vpnclient.exe"), 1700: (900, "musicplayer.exe")}


class DemoMixin:
    def demo_net(self):
        r = lambda proto, l, lp, rem, rp, st, pid: {"proto": proto, "local": l, "lport": lp, "remote": rem,  # noqa
                                                    "rport": rp, "state": st, "pid": pid}
        rows = [r("TCP", "127.0.0.1", 8090, "0.0.0.0", 0, "LISTENING", 1200),
                r("TCP", "0.0.0.0", 8188, "0.0.0.0", 0, "LISTENING", 1200),
                r("TCP", "127.0.0.1", 8081, "0.0.0.0", 0, "LISTENING", 1300),
                r("TCP", "192.0.2.20", 50110, "203.0.113.81", 443, "ESTABLISHED", 1400),
                r("TCP", "192.0.2.20", 50111, "203.0.113.206", 443, "ESTABLISHED", 1500),
                r("TCP", "192.0.2.20", 50112, "203.0.113.14", 443, "ESTABLISHED", 1500),
                r("UDP", "0.0.0.0", 41641, "*", 0, "", 1600),
                r("TCP", "192.0.2.103", 50120, "198.51.100.9", 22, "ESTABLISHED", 1600),
                r("TCP", "192.0.2.20", 50130, "203.0.113.25", 443, "ESTABLISHED", 1700),
                r("TCP", "127.0.0.1", 50140, "127.0.0.1", 8090, "ESTABLISHED", 1400)]
        return rows, dict(DEMO_PROCS)

    def demo_seed(self):
        now = time.time()
        d = os.path.join(self.state_dir, "demo")
        os.makedirs(d, exist_ok=True)
        a, b = os.path.join(d, "presets.json"), os.path.join(d, "settings.json")
        for p in (a, b):
            with open(p, "w", encoding="utf-8") as fh:
                fh.write('{"demo": true}\n')
            with open(p.replace(".json", ".good.json"), "w", encoding="utf-8") as fh:
                fh.write('{"demo": true}\n')
        base = os.path.join(d, "baseline-hashes.csv")
        integrity.write_baseline(base, [{"Algorithm": "SHA256", "Hash": integrity.sha256_file(p), "Path": p}
                                        for p in (a, b)], True)
        with open(b, "a", encoding="utf-8") as fh:
            fh.write("// changed\n")
        self.integrity = integrity.IntegrityMonitor(base, [{"path": a, "good": a.replace(".json", ".good.json")},
                                                           {"path": b, "good": b.replace(".json", ".good.json")}], 10)
        for st in self.integrity.check(force=True):
            self.on_tamper(st, test=True)
        self.raise_alert({"kind": "ai_outbound", "severity": "high",
                          "title": "AI app connected to the internet without approval",
                          "image": r"%~dp0..\..\python\python.exe",
                          "pid": 1200, "remote_ip": "1.1.1.1", "remote_port": 443, "local_port": 50200,
                          "proto": "TCP", "direction": "out", "details": {}, "want_kill": False,
                          "event_time": now, "event_id": 3, "source": "demo"}, test=True)
        self.alerts[0]["action"] = "CLOSED python.exe (pid 1200) + 1 child process"
        self.alerts[0]["enrichment"].update(reverse_dns="one.one.one.one", complete=True,
                                            geo={"country": "AU", "city": "Sydney", "network": "AS13335 Cloudflare"},
                                            traceroute={"hops": [{"hop": 1, "ip": "192.0.2.1"},
                                                                 {"hop": 2, "ip": "10.10.0.1"},
                                                                 {"hop": 3, "ip": "1.1.1.1"}]})
        for i, port in enumerate([22, 23, 80, 135, 139, 443, 445, 3389, 5900, 8080, 8090, 8188]):
            self.on_inbound("203.0.113.50", port, "TCP", now - 30 + i, test=True)
        for i in range(25):
            self.on_inbound("198.51.100.%d" % (i % 4 + 7), 3389, "TCP", now - 300 + i * 9)
        self.outbound_blocked["llama-server.exe"] = {"app": "llama-server.exe", "path": "", "count": 3, "ai": True,
                                                     "last_remote": "185.199.108.133:443", "last": now - 60}
        self.outbound_blocked["svchost.exe"] = {"app": "svchost.exe", "path": "", "count": 41, "ai": False,
                                                "last_remote": "239.255.255.250:1900", "last": now - 5}
        self.sysmon.state, self.sysmon.msg = "ok", "demo"
        self.security.state, self.security.msg = "ok", "demo"
        self.pfw.state, self.pfw.msg = "warn", "demo: pfirewall.log not found"
