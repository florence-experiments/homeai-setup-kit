"""Engine part: button actions (popup + dashboard) and safe self-tests."""
import ipaddress
import os
import shutil
import time

import integrity
import parsers
import winutil


class ActionsMixin:
    def action(self, action, alert_id=None, req=None):
        """Handles a button click. Returns (ok, message)."""
        req = req or {}
        a = self.alert_index.get(alert_id) if alert_id else None
        try:
            if action == "dismiss":
                if not a:
                    return False, "alert not found"
                a["dismissed"] = True
                return True, "dismissed"
            if action == "pause":
                mins = int(req.get("minutes") or self.cfg.get("actions", {}).get("pause_minutes_default", 30))
                self.kill_paused_until = time.time() + max(1, min(mins, 240)) * 60
                self.log.write("pause", minutes=mins)
                return True, "Auto-close paused for %d minutes (alerts still show)." % mins
            if action == "resume":
                self.kill_paused_until = 0
                self.log.write("resume")
                return True, "Auto-close is back on."
            if action == "allow_app":
                return self._allow_app(a)
            if action in ("restore", "accept"):
                return self._file_action(action, a)
            if action == "block_ip":
                return self._block_ip(a)
            if action == "shutdown":
                self.log.write("shutdown", reason="requested from monitor page")
                self.stop_event.set()
                return True, "Watcher is stopping."
            return False, "unknown action: %s" % action
        finally:
            if action != "dismiss":
                self.log.write("click", action=action, alert_id=alert_id)

    def _allow_app(self, a):
        if not a or not a.get("image"):
            return False, "no program on this alert"
        if a.get("test"):
            return False, "test alerts can't add apps"
        path = a["image"]
        allowed = self.cfg.setdefault("allowed_apps", [])
        if path.lower() not in {x.lower() for x in allowed}:
            allowed.append(path)
            self._save_cfg()
            self.rules.reload(self.cfg)
        a["action"] = (a.get("action") + " / " if a.get("action") else "") + "app allowed"
        return True, "Allowed: %s\n(Undo by removing it from allowed_apps in config.json.)" % path

    def _file_action(self, action, a):
        if not a or a.get("kind") != "file_tamper":
            return False, "not a file alert"
        path = (a.get("details") or {}).get("path", "")
        mon = self.test_integrity if a.get("test") and self.test_integrity else self.integrity
        ok, msg = mon.restore(path) if action == "restore" else mon.accept(path)
        if ok:
            a["action"] = "file restored" if action == "restore" else "change accepted"
            a["dismissed"] = True
        return ok, msg

    # ------------------------------------------------------------------ optional firewall block (click only)
    def can_block(self, ip):
        try:
            ipa = ipaddress.ip_address(parsers.clean_ip(ip) or "")
        except ValueError:
            return False, "not a valid IP address"
        ip = str(ipa)
        if ip in self.own_ips or ip in set(self.gateways):
            return False, "that is this PC or the router - never blocked"
        if ip in parsers.NetSet(self.cfg.get("never_block_ips", [])):
            return False, "that address is on the never-block list"
        if ip in self.rules.trusted:
            return False, "local network / Tailscale addresses are never blocked automatically"
        if ipa.is_multicast or ipa.is_unspecified or ipa.is_loopback:
            return False, "special address - not blocked"
        return True, ip

    def _block_ip(self, a):
        if not a or a.get("kind") != "port_scan":
            return False, "only port-scan alerts offer blocking"
        ok, ip = self.can_block(a.get("remote_ip", ""))
        if not ok:
            return False, ip
        if a.get("test"):
            a["action"] = "TEST: would block " + ip
            return True, "Test alert: no rule was added (it would be named 'Blocked by Monitor %s')." % ip
        if not winutil.is_admin():
            return False, "the watcher is not running as administrator, so it can't add firewall rules"
        name = "Blocked by Monitor %s" % ip
        rc, out = winutil.run(["netsh", "advfirewall", "firewall", "add", "rule", "name=" + name,
                               "dir=in", "action=block", "remoteip=" + ip], timeout=20)
        text = parsers.decode_output(out).strip()
        self.log.write("block_ip", ip=ip, rule=name, rc=rc, output=text[:200])
        if rc != 0:
            return False, "netsh failed: " + text[:200]
        a["action"] = "blocked by firewall rule"
        return True, ("Added inbound block rule '%s'.\nRemove it in Windows Firewall (or WFC) "
                      "under Inbound Rules if you change your mind." % name)
