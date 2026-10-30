"""Engine part: turns Sysmon / Security-log / pfirewall records into alerts."""
import ntpath
import re
import time

import parsers
import rules
import winutil


class HandlersMixin:
    # ------------------------------------------------------------------ event handlers
    def on_sysmon(self, ev):
        self.counters["sysmon_events"] += 1
        d = ev.get("data", {})
        if ev.get("event_id") == 22:
            self._remember_dns(d.get("QueryName", ""), d.get("QueryResults", ""))
        for f in self.rules.sysmon(ev):
            self.raise_alert(f)

    def _remember_dns(self, name, results):
        if not name or not results:
            return
        for m in re.finditer(r"(?:::ffff:)?(\d{1,3}(?:\.\d{1,3}){3})|([0-9a-fA-F]{1,4}(?::[0-9a-fA-F]{0,4}){2,7})", results):
            ip = parsers.clean_ip(m.group(1) or m.group(2))
            if ip:
                if not self.dns_cache.get(ip):
                    self.dns_order.append(ip)
                    if len(self.dns_order) >= self.dns_order.maxlen:
                        old = self.dns_order.popleft()
                        self.dns_cache.pop(old, None)
                self.dns_cache[ip].add(name.rstrip("."))

    def on_wfp(self, ev, inbound_too):
        self.counters["security_events"] += 1
        app = ev.get("data", {}).get("Application", "")
        rec, findings = self.rules.wfp(ev, winutil.device_to_dos(app) if app else "")
        if rec["direction"] == "out":
            name = ntpath.basename(rec["app"]) or "(unknown)"
            with self.lock:
                o = self.outbound_blocked.setdefault(name, {"app": name, "path": rec["app"], "count": 0,
                                                            "ai": self.rules.is_ai(rec["app"])})
                o["count"] += 1
                o["last_remote"] = "%s:%s" % (rec["remote"], rec["rport"])
                o["last"] = rec["ts"]
        elif rec["direction"] == "in" and inbound_too and rec["remote"]:
            self.on_inbound(rec["remote"], rec["lport"], rec["proto"], rec["ts"] or time.time())
        for f in findings:
            self.raise_alert(f)

    def on_pfirewall(self, rec, test=False):
        self.counters["pfirewall_lines"] += 1
        if rec["action"] != "DROP" or rec["path"] != "RECEIVE":
            return
        if rec["src"] in self.own_ips or parsers.is_multicast_or_broadcast(rec["dst"] or ""):
            return
        self.on_inbound(rec["src"], rec["dport"], rec["proto"], rec["ts"], test=test)

    def on_inbound(self, ip, port, proto, ts, test=False):
        ignore = parsers.NetSet(self.cfg.get("port_scan", {}).get("ignore_ips", []))
        with self.lock:
            self.inbound.add(ip, port, proto, ts)
            self.inbound_minute[ip] += 1
            hit = None if ip in ignore or port is None else self.scan.add(ip, port, ts)
            if hit:
                s = self.inbound.by_ip.get(ip)
                if s:
                    s["scan"] = True
        if hit:
            f = rules.Rules._f("port_scan", "high", "Port scan: %d different ports probed in %ds" %
                               (hit["count"], hit["window"]), {"time": ts, "event_id": None,
                                                                "channel": "pfirewall.log"},
                               remote_ip=ip, proto=proto, direction="in",
                               details={"ports": hit["ports"][:40],
                                        "note": "The firewall already dropped these. Blocking the IP is optional."})
            f["can_block"] = self.can_block(ip)[0]
            self.raise_alert(f, test=test)

    # ------------------------------------------------------------------ alerts
    def raise_alert(self, f, test=False):
        now = time.time()
        if f.get("pid") in self.expect_test_pids:
            test = True
        key = (f["kind"], (f.get("image") or "").lower(), f.get("remote_ip") or "", f.get("details", {}).get("path", ""))
        cd = self.cfg.get("alerts", {}).get("cooldown_seconds", 300)
        with self.lock:
            prev = self.cooldown.get(key)
            if prev and now - prev["at"] < cd:
                prev["alert"]["repeats"] = prev["alert"].get("repeats", 0) + 1
                prev["alert"]["last_seen"] = now
                if f.get("want_kill"):        # still close a repeat offender, just don't pop up again
                    self._maybe_kill(dict(f), prev["alert"])
                return prev["alert"]
            self.counters["alerts"] += 1
            a = dict(f)
            a.update(id="a%d-%d" % (int(now), self.counters["alerts"]), time=now, test=bool(test),
                     dismissed=False, action="", repeats=0, enrichment={})
            self.cooldown[key] = {"at": now, "alert": a}
            self.alerts.appendleft(a)
            self.alert_index[a["id"]] = a
            if len(self.alert_index) > 600:
                live = {x["id"] for x in self.alerts}
                self.alert_index = {k: v for k, v in self.alert_index.items() if k in live}
        if a.get("want_kill"):
            self._maybe_kill(f, a)
        self.log.write("alert", **{k: v for k, v in a.items() if k != "enrichment"})
        if a.get("remote_ip"):
            self.enricher.submit(a, self._enriched, skip_network=test)
            if test:
                a["enrichment"]["complete"] = True
        else:
            a["enrichment"]["complete"] = True
        sev = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        need = sev.get(self.cfg.get("alerts", {}).get("popup_min_severity", "high"), 2)
        if sev.get(a.get("severity"), 1) >= need:
            self.popups.show(a)
        return a

    def _enriched(self, a):
        e = a.get("enrichment", {})
        self.log.write("enrichment", alert_id=a["id"], remote_ip=a.get("remote_ip"),
                       enrichment={k: v for k, v in e.items() if k != "complete"})


    def on_tamper(self, st, test=False):
        state = st.get("state")
        title = ("Protected HomeAI file was CHANGED" if state == "CHANGED"
                 else "Protected HomeAI file is MISSING")
        f = rules.Rules._f("file_tamper", "high", title, {"time": time.time(), "event_id": None,
                                                         "channel": "integrity"},
                           image=st.get("path", ""),
                           details={"path": st.get("path"), "file": st.get("path"), "expected": st.get("expected"),
                                    "actual": st.get("actual"), "good_copy": st.get("good"),
                                    "good_exists": st.get("good_exists"),
                                    "note": "Nothing was restored automatically. Click Restore file, or "
                                            "'This change was me' if you edited it."})
        self.raise_alert(f, test=test)
