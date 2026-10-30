"""Engine part: builds the JSON the Security Monitor page shows (/api/state)."""
import ntpath
import os
import time

import parsers
import winutil

LOCAL_BINDS = ("127.0.0.1", "::1", "[::1]")


def _uptime(sec):
    sec = int(sec)
    if sec < 3600:
        return "%dm" % (sec // 60)
    if sec < 86400:
        return "%dh %dm" % (sec // 3600, sec % 3600 // 60)
    return "%dd %dh" % (sec // 86400, sec % 86400 // 3600)


class StateMixin:
    def _netstat(self):
        """netstat -ano + process list, at most every 4 s, and only while the page is open."""
        now = time.time()
        if now - self.net_cache["at"] < 4:
            return self.net_cache
        rows, procs = [], {}
        if winutil.IS_WIN:
            rc, out = winutil.run(["netstat", "-ano"], timeout=15)
            rows = parsers.parse_netstat(out) if rc == 0 else []
            procs = winutil.list_processes()
        elif self.demo:
            rows, procs = self.demo_net()
        self.net_cache = {"at": now, "rows": rows, "procs": procs}
        return self.net_cache

    def _image(self, pid, procs):
        img = self.images.get(pid)
        name = procs.get(pid, (0, ""))[1]
        if img is None or ntpath.basename(img).lower() != name.lower():
            img = winutil.process_image(pid) or name
            self.images[pid] = img
            if len(self.images) > 2000:
                self.images.clear()
        return img or name

    def _traffic_and_exposure(self):
        net = self._netstat()
        rows, procs = net["rows"], net["procs"]
        ai_ports = {int(k): v for k, v in self.cfg.get("ai_ports", {}).items()}
        exposure, by_pid = [], {}
        for r in rows:
            if r["state"] == "LISTENING" and r["lport"] in ai_ports:
                exposure.append({"name": ai_ports[r["lport"]], "port": r["lport"], "bind": r["local"],
                                 "exposed": r["local"] not in LOCAL_BINDS, "pid": r["pid"]})
            pid = r["pid"]
            if pid is None:
                continue
            p = by_pid.setdefault(pid, {"pid": pid, "established": 0, "listening": 0, "remotes": []})
            if r["state"] == "LISTENING":
                p["listening"] += 1
            elif r["state"] == "ESTABLISHED":
                p["established"] += 1
                if r["remote"] not in LOCAL_BINDS and len(p["remotes"]) < 6:
                    p["remotes"].append({"ip": r["remote"], "port": r["rport"],
                                         "external": self.rules.is_external(r["remote"])})
        seen, uniq = set(), []
        for x in sorted(exposure, key=lambda e: (not e["exposed"], e["port"])):
            k = (x["port"], x["bind"])
            if k not in seen:
                seen.add(k)
                uniq.append(x)
        traffic = []
        for pid, p in by_pid.items():
            if not p["established"] and not p["listening"]:
                continue
            img = self._image(pid, procs) if pid > 4 else ("System" if pid == 4 else "Idle")
            p.update(name=ntpath.basename(img) or "pid %d" % pid, path=img, ai=self.rules.is_ai(img),
                     allowed=self.rules.is_allowed(img))
            traffic.append(p)
        traffic.sort(key=lambda p: (not p["ai"], -sum(r["external"] for r in p["remotes"]), -p["established"]))
        return traffic[:30], uniq

    def _health(self):
        now = time.time()
        t0, c0 = self.cpu_mark
        if now - t0 >= 2:
            c1 = time.process_time()
            self.cpu_pct = round(100.0 * (c1 - c0) / (now - t0) / max(1, os.cpu_count() or 1), 2)
            self.cpu_mark = (now, c1)
        h = {"watcher": {"ok": not self.loop_error, "uptime": _uptime(now - self.started), "cpu_pct": self.cpu_pct,
                         "mem_mb": round(winutil.memory_mb() or 0, 1), "error": self.loop_error, "version": self.version},
             "admin": winutil.is_admin() or self.demo}
        src = self.cfg.get("sources", {})
        for key, tail, flag in (("sysmon", self.sysmon, "sysmon"), ("security", self.security, "security_log"),
                                ("pfirewall", self.pfw, "pfirewall")):
            if not src.get(flag, True):
                h[key] = {"state": "off", "msg": "turned off in config.json"}
            else:
                h[key] = {"state": tail.state, "msg": tail.msg}
        if self.sysmon_service is False:
            h["sysmon"] = {"state": "bad", "msg": "Sysmon service is not running (run Install-All.cmd)"}
        if not self.cfg.get("enrichment", {}).get("offline_geo", True):
            h["geo"] = {"state": "off", "msg": "offline geo-IP turned off"}
        elif self.geo.loaded:
            h["geo"] = {"state": "ok", "msg": "loaded: " + ", ".join(ntpath.basename(f) for f in self.geo.files)}
        else:
            h["geo"] = {"state": "warn", "msg": self.geo.error or "loading..."}
        snap = self.integrity.snapshot()
        states = [f.get("state") for f in snap["files"]]
        if not self.cfg.get("integrity", {}).get("enabled", True):
            h["integrity"] = {"state": "off", "msg": "turned off"}
        elif any(s in ("CHANGED", "MISSING") for s in states):
            h["integrity"] = {"state": "bad", "msg": "a protected file changed"}
        elif snap["baseline_error"] or any(s != "OK" for s in states):
            h["integrity"] = {"state": "warn", "msg": snap["baseline_error"] or "some files have no baseline"}
        else:
            h["integrity"] = {"state": "ok", "msg": "%d files match the baseline" % len(states)}
        return h, snap

    version = ""

    def state(self):
        now = time.time()
        self.dashboard_seen = now
        health, snap = self._health()
        traffic, exposure = self._traffic_and_exposure()
        if not winutil.IS_WIN and not self.demo:
            note = "live connections are only available on Windows"
        else:
            note = "No connections right now."
        with self.lock:
            alerts = [dict(a, enrichment=dict(a.get("enrichment") or {})) for a in list(self.alerts)[:40]]
            inbound = self.inbound.top(25)
            total = self.inbound.total
            outbound = sorted(self.outbound_blocked.values(), key=lambda o: -o["count"])[:20]
        for r in inbound:
            if self.cfg.get("enrichment", {}).get("offline_geo", True) and self.geo.loaded:
                r["geo"] = self.geo.lookup(r["ip"])
        recent_bad = [a for a in alerts if not a["dismissed"] and not a["test"] and a["severity"] == "high"
                      and now - a["time"] < 3600]
        bad_health = [k for k, v in health.items() if isinstance(v, dict) and v.get("state") == "bad"]
        if recent_bad:
            status = {"text": "%d alert%s need a look" % (len(recent_bad), "s" if len(recent_bad) > 1 else ""),
                      "tone": "bad"}
        elif bad_health or not health["watcher"]["ok"]:
            status = {"text": "Watching, with problems: " + ", ".join(bad_health or ["watcher"]), "tone": "warn"}
        else:
            status = {"text": "All quiet - watching", "tone": "ok"}
        acts = self.cfg.get("actions", {})
        on = bool(acts.get("kill_ai_on_unapproved_outbound", True))
        if self.closing_paused():
            kill = {"on": on, "paused": True,
                    "text": "Auto-close paused until " + parsers.fmt_local(self.kill_paused_until)[11:16]}
        else:
            kill = {"on": on, "paused": False,
                    "text": "Auto-close AI apps: ON" if on else "Auto-close AI apps: OFF (alerts only)"}
        return {"now": now, "status": status, "kill": kill, "health": health, "alerts": alerts,
                "integrity": snap, "exposure": exposure, "traffic": traffic, "traffic_note": note,
                "inbound": inbound, "inbound_total": total, "outbound": outbound,
                "counters": dict(self.counters)}
