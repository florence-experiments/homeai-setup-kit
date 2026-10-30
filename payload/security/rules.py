"""Detection rules. Pure functions over parsed events, so they can be unit-tested off Windows.
The engine (watcher.py) decides what to do with each finding (kill, popup, log)."""
import ntpath
import re

import parsers

SEV_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3}
SHELLS = {"cmd.exe", "powershell.exe", "pwsh.exe", "wscript.exe", "cscript.exe", "mshta.exe",
          "curl.exe", "wget.exe", "bitsadmin.exe", "certutil.exe", "rundll32.exe", "regsvr32.exe"}


def base(path):
    return ntpath.basename(path or "").lower()



# Harmless command Python runs by itself (Windows version check)
_HARMLESS_SHELL = __import__("re").compile(r'^"?[A-Za-z]:\\windows\\system32\\cmd\.exe"?\s+/c\s+"?ver"?$', __import__("re").I)

class Rules:
    def __init__(self, cfg, own_pid=0, own_ips=()):
        self.cfg = cfg
        self.own_pid = own_pid
        self.own_ips = set(own_ips)
        self.reload(cfg)

    def reload(self, cfg):
        self.cfg = cfg
        self.trusted = parsers.NetSet(cfg.get("trusted_networks", []))
        ai = cfg.get("ai_processes", {})
        self.ai_names = {n.lower() for n in ai.get("image_names", [])}
        self.ai_paths = [p.lower() for p in ai.get("path_contains", [])]
        nk = cfg.get("never_kill", {})
        self.nk_names = {n.lower() for n in nk.get("image_names", [])}
        self.nk_paths = [p.lower() for p in nk.get("path_contains", [])]
        self.allowed = {a.lower() for a in cfg.get("allowed_apps", [])}
        sc = cfg.get("screenshot", {})
        self.sc_enabled = sc.get("enabled", True)
        self.sc_tools = {n.lower() for n in sc.get("suspicious_tools", [])}
        self.sc_user_tools = {n.lower() for n in sc.get("user_tools_allowlist", [])}
        self.sc_patterns = [re.compile(p, re.I) for p in sc.get("cmdline_patterns", [])]
        self.sc_dlls = {d.lower() for d in sc.get("image_load_dlls", [])}
        self.sc_allow_apps = {a.lower() for a in sc.get("capture_apps_allowlist", [])}
        self.shell_ok = [(p.lower(), " ".join(c.lower().split())) for p, c in
                         ((x.get("parent", ""), x.get("command_line", "")) for x in cfg.get("ai_shell_allowlist", []))]

    def _shell_ok(self, parent, cmd):
        """Exact (parent path, command line) pairs you approved, e.g. HomeAI secure-delete TRIM."""
        key = (parent.lower(), " ".join(cmd.lower().split()))
        return key in self.shell_ok

    # ------------------------------------------------------------------ classification
    def is_ai(self, image):
        low = (image or "").lower()
        return base(low) in self.ai_names or any(p in low for p in self.ai_paths)

    def is_never_kill(self, image):
        low = (image or "").lower()
        return base(low) in self.nk_names or any(p in low for p in self.nk_paths)

    def is_allowed(self, image):
        low = (image or "").lower()
        return low in self.allowed or base(low) in self.allowed

    def is_external(self, ip):
        ip = parsers.clean_ip(ip)
        return bool(ip) and ip not in self.trusted and ip not in self.own_ips

    # ------------------------------------------------------------------ Sysmon
    def sysmon(self, ev):
        eid, d = ev.get("event_id"), ev.get("data", {})
        pid = parsers._int(d.get("ProcessId"))
        if pid == self.own_pid:
            return []
        if eid == 3:
            return self._sysmon_net(ev, d, pid)
        if eid == 1:
            return self._sysmon_proc(ev, d, pid)
        if eid == 7:
            return self._sysmon_imageload(ev, d, pid)
        if eid == 22:
            return self._sysmon_dns(ev, d, pid)
        if eid == 8:
            src, tgt = d.get("SourceImage", ""), d.get("TargetImage", "")
            if self.is_allowed(src):
                return []
            sev = "high" if self.is_ai(src) or self.is_ai(tgt) else "medium"
            return [self._f("remote_thread", sev, "Code injected into another program",
                            ev, image=src, pid=parsers._int(d.get("SourceProcessId")),
                            details={"target": tgt, "target_pid": d.get("TargetProcessId", "")})]
        if eid == 10:
            tgt = d.get("TargetImage", "")
            src = d.get("SourceImage", "")
            if base(tgt) == "lsass.exe" and not self.is_never_kill(src) and not self.is_allowed(src):
                return [self._f("lsass_access", "high", "A program opened the Windows password process (lsass)",
                                ev, image=src, pid=parsers._int(d.get("SourceProcessId")),
                                details={"access": d.get("GrantedAccess", "")})]
        return []

    def _sysmon_net(self, ev, d, pid):
        image = d.get("Image", "")
        initiated = (d.get("Initiated", "").lower() == "true")
        remote = d.get("DestinationIp") if initiated else d.get("SourceIp")
        rport = d.get("DestinationPort") if initiated else d.get("SourcePort")
        lport = d.get("SourcePort") if initiated else d.get("DestinationPort")
        remote = parsers.clean_ip(remote)
        if not self.is_ai(image) or self.is_allowed(image) or not self.is_external(remote):
            return []
        acts = self.cfg.get("actions", {})
        if initiated:
            return [self._f("ai_outbound", "high", "AI app connected to the internet without approval", ev,
                            image=image, pid=pid, remote_ip=remote, remote_port=parsers._int(rport),
                            local_port=parsers._int(lport), proto=d.get("Protocol", "").upper(), direction="out",
                            details={"hostname": d.get("DestinationHostname", ""), "user": d.get("User", "")},
                            kill=acts.get("kill_ai_on_unapproved_outbound", True))]
        return [self._f("ai_inbound_accepted", "high", "Someone outside connected INTO an AI app", ev,
                        image=image, pid=pid, remote_ip=remote, remote_port=parsers._int(rport),
                        local_port=parsers._int(lport), proto=d.get("Protocol", "").upper(), direction="in",
                        details={"hint": "the AI server is probably listening on 0.0.0.0; bind it to 127.0.0.1"},
                        kill=acts.get("kill_on_inbound_accept", False))]

    def _sysmon_proc(self, ev, d, pid):
        image, parent, cmd = d.get("Image", ""), d.get("ParentImage", ""), d.get("CommandLine", "")
        out = []
        b = base(image)
        if self.sc_enabled and not self.is_allowed(image):
            hit = None
            if b in self.sc_tools:
                hit = "known screen-capture tool started"
            elif b not in self.sc_user_tools and any(p.search(cmd) for p in self.sc_patterns):
                hit = "command line looks like it takes a screenshot"
            if hit:
                sev = "high" if self.is_ai(parent) else "medium"
                out.append(self._f("screenshot", sev, "Possible screenshot: " + hit, ev, image=image, pid=pid,
                                   details={"command_line": cmd[:500], "parent": parent}))
        if self.is_ai(parent) and b in SHELLS and not self.is_allowed(parent) and not _HARMLESS_SHELL.match(cmd.strip()) \
                and not self._shell_ok(parent, cmd):
            out.append(self._f("ai_spawned_shell", "high", "AI app started a shell or downloader", ev,
                               image=image, pid=pid,
                               details={"command_line": cmd[:500], "parent": parent,
                                        "parent_pid": d.get("ParentProcessId", "")}))
        return out

    def _sysmon_imageload(self, ev, d, pid):
        if not self.sc_enabled:
            return []
        image, dll = d.get("Image", ""), d.get("ImageLoaded", "")
        if base(dll) not in self.sc_dlls:
            return []
        if self.is_allowed(image) or base(image) in self.sc_allow_apps or base(image) in self.sc_user_tools:
            return []
        sev = "high" if self.is_ai(image) else "medium"
        return [self._f("screenshot", sev, "Possible screen capture: program loaded the capture library", ev,
                        image=image, pid=pid, details={"library": dll})]

    def _sysmon_dns(self, ev, d, pid):
        image, name = d.get("Image", ""), d.get("QueryName", "")
        if not self.is_ai(image) or self.is_allowed(image) or not name:
            return []
        low = name.lower().rstrip(".")
        if low in ("localhost",) or low.endswith((".local", ".lan", ".ts.net", ".home.arpa")) or "." not in low:
            return []
        return [self._f("ai_dns", "medium", "AI app looked up an internet name", ev, image=image, pid=pid,
                        details={"query": name, "results": d.get("QueryResults", "")[:300]})]

    # ------------------------------------------------------------------ Security log 5152/5157
    def wfp(self, ev, app_dos_path=""):
        d = ev.get("data", {})
        direction = parsers.wfp_direction(d.get("Direction"))
        src, dst = parsers.clean_ip(d.get("SourceAddress")), parsers.clean_ip(d.get("DestAddress"))
        sport, dport = parsers._int(d.get("SourcePort")), parsers._int(d.get("DestPort"))
        # Work out which side is remote. Prefer "the side that is not one of my own IPs";
        # fall back to the usual WFP layout (outbound: Dest is remote, inbound: Source is remote).
        if src in self.own_ips and dst not in self.own_ips:
            remote_is_dst = True
        elif dst in self.own_ips and src not in self.own_ips:
            remote_is_dst = False
        else:
            remote_is_dst = direction != "in"
        if remote_is_dst:
            remote, rport, lport = dst, dport, sport
        else:
            remote, rport, lport = src, sport, dport
        proto = parsers.PROTO_NAMES.get(d.get("Protocol", ""), d.get("Protocol", ""))
        app = app_dos_path or d.get("Application", "")
        pid = parsers._int(d.get("ProcessID") or d.get("ProcessId"))
        rec = {"direction": direction, "remote": remote, "rport": rport, "lport": lport, "proto": proto,
               "app": app, "pid": pid, "ts": ev.get("time"), "event_id": ev.get("event_id")}
        findings = []
        if (direction == "out" and pid != self.own_pid and self.is_ai(app) and not self.is_allowed(app)
                and self.is_external(remote)):
            findings.append(self._f("ai_outbound_blocked", "high",
                                    "AI app tried to reach the internet (firewall blocked it)", ev,
                                    image=app, pid=pid, remote_ip=remote, remote_port=rport, local_port=lport,
                                    proto=proto, direction="out",
                                    kill=self.cfg.get("actions", {}).get("kill_on_blocked_attempt", True)))
        return rec, findings

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _f(kind, severity, title, ev, image="", pid=None, remote_ip="", remote_port=None, local_port=None,
           proto="", direction="", details=None, kill=False):
        return {"kind": kind, "severity": severity, "title": title, "image": image, "pid": pid,
                "remote_ip": remote_ip, "remote_port": remote_port, "local_port": local_port, "proto": proto,
                "direction": direction, "details": details or {}, "want_kill": bool(kill),
                "event_time": ev.get("time"), "event_id": ev.get("event_id"),
                "source": ev.get("channel") or ev.get("provider") or ""}
