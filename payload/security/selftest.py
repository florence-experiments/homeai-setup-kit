"""Engine part: safe self-tests used by Test-Watcher.cmd (nothing real is changed)."""
import os
import shutil
import time

import integrity
import parsers
import winutil


class SelfTestMixin:

    # ------------------------------------------------------------------ self-tests (Test-Watcher.cmd)
    def run_test(self, kind, req=None):
        req = req or {}
        now = time.time()
        if kind == "expect_pid":
            pid = int(req.get("pid") or 0)
            if pid <= 4:
                return False, "bad pid"
            self.expect_test_pids[pid] = now + 180
            return True, "alerts for pid %d will be marked TEST" % pid
        if kind == "outbound":
            return self._test_outbound(int(req.get("pid") or 0), now)
        if kind == "tamper":
            return self._test_tamper()
        if kind == "scan":
            return self._test_scan(now)
        if kind == "popup":
            f = {"kind": "test", "severity": "high", "title": "Test alert - everything is working",
                 "image": "", "pid": None, "remote_ip": "", "details": {"note": "Safe test. Nothing happened."},
                 "want_kill": False, "event_time": now, "event_id": None, "source": "test"}
            self.raise_alert(f, test=True)
            return True, "test popup raised"
        return False, "unknown test: %s" % kind

    def _test_outbound(self, pid, now):
        """Fallback when the real Sysmon path didn't catch the dummy: feed a synthetic event 3 for it,
        so the rule + close path is still exercised. Only for a live AI-type process."""
        image = winutil.process_image(pid) if pid > 4 else ""
        if not image:
            return False, "dummy process not found"
        if not self.rules.is_ai(image):
            return False, "refused: pid %d is not an AI-type process (%s)" % (pid, image)
        self.expect_test_pids[pid] = now + 180
        ev = {"event_id": 3, "time": now, "channel": "TEST (synthetic)", "data": {
            "Image": image, "ProcessId": str(pid), "Initiated": "true", "Protocol": "tcp",
            "SourceIp": "127.0.0.1", "SourcePort": "50000", "DestinationIp": "1.1.1.1", "DestinationPort": "443"}}
        found = self.rules.sysmon(ev)
        if not found:
            return False, "the rule did not match (is the dummy's path in allowed_apps?)"
        for f in found:
            self.raise_alert(f, test=True)
        return True, "synthetic outbound event raised for pid %d" % pid

    def _test_tamper(self):
        """Makes a throw-away copy of a protected file in state\\selftest, records its hash,
        changes the copy and lets the normal integrity check find it. Real files are not touched."""
        d = os.path.join(self.state_dir, "selftest")
        os.makedirs(d, exist_ok=True)
        live, good = os.path.join(d, "presets.json"), os.path.join(d, "presets.good.json")
        real = next((f["path"] for f in self.cfg.get("integrity", {}).get("files", []) if os.path.exists(f["path"])), "")
        if real:
            shutil.copy2(real, live)
        else:
            with open(live, "w", encoding="utf-8") as fh:
                fh.write('{"test": true}\n')
        shutil.copy2(live, good)
        base = os.path.join(d, "baseline-hashes.csv")
        integrity.write_baseline(base, [{"Algorithm": "SHA256", "Hash": integrity.sha256_file(live), "Path": live}], True)
        mon = integrity.IntegrityMonitor(base, [{"path": live, "good": good}], interval=0)
        mon.check(force=True)
        with open(live, "a", encoding="utf-8") as fh:
            fh.write("\n// test change %s\n" % time.strftime("%H:%M:%S"))
        self.test_integrity = mon
        hits = mon.check(force=True)
        for st in hits:
            self.on_tamper(st, test=True)
        if not hits:
            return False, "the change was not detected"
        return True, "fake change detected on %s (click Restore file in the popup to test restore)" % live

    def _test_scan(self, now):
        ip = "203.0.113.%d" % (int(now) % 200 + 20)   # TEST-NET-3: documentation range, never real
        me = next((i for i in sorted(self.own_ips) if "." in i and not i.startswith("127.")), "192.0.2.2")
        p = parsers.PfirewallParser()
        n = 0
        for port in range(1001, 1013):
            rec = p.feed("%s DROP TCP %s %s 40000 %d 52 S 0 0 1024 - - - RECEIVE" %
                         (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)), ip, me, port))
            if rec:
                self.on_pfirewall(rec, test=True)
                n += 1
        return n > 0, "fed %d fake blocked lines from %s" % (n, ip)
