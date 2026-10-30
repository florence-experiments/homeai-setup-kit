"""Alert enrichment: offline geo (DB-IP Lite CSV), reverse DNS, optional online geo, traceroute.

Privacy notes (also in README):
  * Offline geo reads a local file, so nothing leaves the PC.
  * Reverse DNS asks your normal DNS server one question about the IP.
  * Traceroute sends small ICMP probes toward the IP (no data from your PC).
  * Online geo (ip-api.com) is OFF by default; if switched on it sends the IP to ip-api.com
    over plain HTTP (their free tier has no HTTPS) and only to hosts in online_lookup_allowlist.
"""
import array
import bisect
import concurrent.futures
import csv
import glob
import gzip
import io
import ipaddress
import json
import os
import socket
import threading
import time
import urllib.parse
import urllib.request

import parsers
import winutil


class GeoDB:
    """Loads DB-IP Lite country and ASN CSV files (dbip-country-lite-YYYY-MM.csv[.gz],
    dbip-asn-lite-YYYY-MM.csv[.gz], optionally dbip-city-lite). License: CC BY 4.0, no account."""

    def __init__(self, geo_dir):
        self.geo_dir = geo_dir
        self.tables = {}      # kind -> {4: (starts, ends, values), 6: (...)}
        self.loaded = False
        self.error = ""
        self.files = []

    @staticmethod
    def _open(path):
        if path.endswith(".gz"):
            return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8", errors="replace")
        return open(path, "r", encoding="utf-8", errors="replace")

    def _latest(self, pattern):
        files = sorted(glob.glob(os.path.join(self.geo_dir, pattern)))
        return files[-1] if files else None

    def load(self):
        try:
            for kind, pattern in (("country", "dbip-country-lite-*.csv*"), ("asn", "dbip-asn-lite-*.csv*"),
                                  ("city", "dbip-city-lite-*.csv*")):
                path = self._latest(pattern)
                if path:
                    self.tables[kind] = self._load_file(path, kind)
                    self.files.append(os.path.basename(path))
            self.loaded = bool(self.tables)
            if not self.loaded:
                self.error = "no DB-IP files in " + self.geo_dir
        except Exception as e:  # never let a bad file stop the watcher
            self.error = "geo load failed: %s" % e
        return self.loaded

    @staticmethod
    def _key(ip_text):
        """(version, int key). IPv6 keeps only the top 64 bits (DB-IP v6 ranges are /64 or wider)."""
        if ":" in ip_text:
            return 6, int.from_bytes(socket.inet_pton(socket.AF_INET6, ip_text)[:8], "big")
        return 4, int.from_bytes(socket.inet_aton(ip_text), "big")

    def _load_file(self, path, kind):
        # Compact arrays keep memory to roughly 16 bytes per range (about 10-20 MB in total).
        tab = {4: (array.array("I"), array.array("I"), []), 6: (array.array("Q"), array.array("Q"), [])}
        intern = {}
        last = {4: -1, 6: -1}
        with self._open(path) as f:
            for row in csv.reader(f):
                if len(row) < 3:
                    continue
                try:
                    va, a = self._key(row[0])
                    vb, b = self._key(row[1])
                except (OSError, ValueError):
                    continue
                if va != vb or a < last[va]:
                    continue          # DB-IP files are sorted; skip anything odd
                last[va] = a
                if kind == "country":
                    val = row[2]
                elif kind == "asn":
                    val = "AS%s %s" % (row[2], row[3] if len(row) > 3 else "")
                else:  # city: start,end,continent,country,state,city,lat,lon
                    val = "%s|%s|%s" % (row[3] if len(row) > 3 else "", row[4] if len(row) > 4 else "",
                                        row[5] if len(row) > 5 else "")
                val = intern.setdefault(val, val)
                s, e, v = tab[va]
                s.append(a)
                e.append(b)
                v.append(val)
        return tab

    def _find(self, kind, ip):
        t = self.tables.get(kind)
        if not t:
            return None
        ver, n = self._key(ip)
        s, e, v = t[ver]
        i = bisect.bisect_right(s, n) - 1
        if i >= 0 and s[i] <= n <= e[i]:
            return v[i]
        return None

    def lookup(self, ip):
        ip = parsers.clean_ip(ip)
        if not ip or not self.loaded:
            return {}
        out = {}
        c = self._find("country", ip)
        if c:
            out["country"] = c
        city = self._find("city", ip)
        if city:
            cc, region, name = city.split("|")
            out.update({"country": cc or out.get("country", ""), "region": region, "city": name})
        asn = self._find("asn", ip)
        if asn:
            out["network"] = asn.strip()
        if out:
            out["source"] = "DB-IP Lite (offline)"
        return out


def reverse_dns(ip, timeout=3.0):
    result = {}

    def work():
        try:
            result["name"] = socket.gethostbyaddr(ip)[0]
        except (socket.herror, socket.gaierror, OSError):
            result["name"] = ""
    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(timeout)
    return result.get("name", "") if not t.is_alive() else "(timeout)"


def online_geo(ip, url_template, allowlist, timeout=4.0):
    url = url_template.format(ip=ip)
    host = urllib.parse.urlparse(url).hostname or ""
    if host.lower() not in [h.lower() for h in allowlist]:
        return {"error": "online lookup host %s is not in online_lookup_allowlist" % host}
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            data = json.loads(r.read(20000).decode("utf-8", "replace"))
        data["source"] = host
        return data
    except Exception as e:
        return {"error": str(e)}


def traceroute(ip, args):
    rc, out = winutil.run(["tracert"] + list(args) + [ip], timeout=60)
    text = parsers.decode_output(out)
    return {"hops": parsers.parse_tracert(text), "raw": text[-4000:]}


class Enricher:
    """Runs lookups in at most 2 background threads, caches results for an hour."""

    def __init__(self, cfg, geo, trusted, dns_cache):
        self.cfg = cfg
        self.geo = geo
        self.trusted = trusted
        self.dns_cache = dns_cache      # ip -> set(domain) from Sysmon event 22
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="enrich")
        self.cache = {}
        self.lock = threading.Lock()

    def quick(self, ip):
        """Instant, offline-only facts (shown in the popup straight away)."""
        info = {"ip": ip}
        if ip in self.trusted:
            info["scope"] = "local / Tailscale"
        else:
            info["scope"] = "internet"
        g = self.geo.lookup(ip) if self.cfg.get("offline_geo", True) else {}
        if g:
            info["geo"] = g
        names = sorted(self.dns_cache.get(ip, ()))[:5]
        if names:
            info["dns_names_seen"] = names
        return info

    def submit(self, alert, on_done, skip_network=False):
        ip = alert.get("remote_ip")
        if not ip:
            return
        alert.setdefault("enrichment", {}).update(self.quick(ip))
        if skip_network:
            alert["enrichment"]["note"] = "test alert: network lookups skipped"
            return
        self.pool.submit(self._slow, alert, ip, on_done)

    def _slow(self, alert, ip, on_done):
        with self.lock:
            cached = self.cache.get(ip)
        if cached and time.time() - cached["at"] < 3600:
            res = cached["res"]
        else:
            res = {}
            private = ip in self.trusted
            if self.cfg.get("reverse_dns", True):
                res["reverse_dns"] = reverse_dns(ip)
            if self.cfg.get("online_geo", False) and not private:
                res["online_geo"] = online_geo(ip, self.cfg.get("online_geo_url", ""),
                                               self.cfg.get("online_lookup_allowlist", []))
            if self.cfg.get("traceroute", True) and (not private or self.cfg.get("traceroute_private", False)):
                alert.setdefault("enrichment", {})["traceroute"] = {"status": "running"}
                res["traceroute"] = traceroute(ip, self.cfg.get("traceroute_args", ["-d", "-h", "15", "-w", "500"]))
            with self.lock:
                self.cache[ip] = {"at": time.time(), "res": res}
        alert.setdefault("enrichment", {}).update(res)
        alert["enrichment"]["complete"] = True
        try:
            on_done(alert)
        except Exception:
            pass
