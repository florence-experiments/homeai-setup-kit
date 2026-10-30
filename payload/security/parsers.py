"""Pure parsing helpers for the Security Watcher (no Windows calls, so they are unit-testable).

Covers: wevtutil XML output (Sysmon + Security log), pfirewall.log lines, netstat -ano,
ipconfig default gateways, tracert output, IP-range checks and port-scan detection.
"""
import calendar
import collections
import datetime
import ipaddress
import re
import time
import xml.etree.ElementTree as ET

EVT_NS = "{http://schemas.microsoft.com/win/2004/08/events/event}"


# ----------------------------------------------------------------------------- decoding
def decode_output(raw):
    """wevtutil/netstat output may be UTF-16, UTF-8 or the OEM code page. Be forgiving."""
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    if len(raw) > 3 and raw[1:2] == b"\x00" and raw[3:4] == b"\x00":
        return raw.decode("utf-16-le", errors="replace")
    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


# ----------------------------------------------------------------------------- time
def parse_utc(text):
    """'2026-10-29T23:10:01.1234567Z' or '2026-10-29 23:10:01.123' (UTC) -> epoch seconds."""
    if not text:
        return None
    t = text.strip().rstrip("Z").replace("T", " ")
    frac = 0.0
    if "." in t:
        t, f = t.split(".", 1)
        f = re.sub(r"\D", "", f)[:6]
        frac = float("0." + f) if f else 0.0
    try:
        st = time.strptime(t, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return calendar.timegm(st) + frac


def parse_local(date_s, time_s):
    """pfirewall.log uses local time by default."""
    try:
        st = time.strptime(date_s + " " + time_s, "%Y-%m-%d %H:%M:%S")
        return time.mktime(st)
    except (ValueError, OverflowError):
        return None


def fmt_local(epoch):
    if epoch is None:
        return ""
    return datetime.datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M:%S")


# ----------------------------------------------------------------------------- event XML
_EVENT_RE = re.compile(r"<Event[\s>].*?</Event>", re.S)


def _event_to_dict(ev):
    sysel = ev.find(EVT_NS + "System")
    out = {"event_id": None, "record_id": None, "time": None, "channel": "", "provider": "", "data": {}}
    if sysel is not None:
        eid = sysel.find(EVT_NS + "EventID")
        if eid is not None and eid.text:
            out["event_id"] = int(eid.text.strip())
        rid = sysel.find(EVT_NS + "EventRecordID")
        if rid is not None and rid.text:
            out["record_id"] = int(rid.text.strip())
        tc = sysel.find(EVT_NS + "TimeCreated")
        if tc is not None:
            out["time"] = parse_utc(tc.get("SystemTime"))
        ch = sysel.find(EVT_NS + "Channel")
        if ch is not None and ch.text:
            out["channel"] = ch.text.strip()
        pr = sysel.find(EVT_NS + "Provider")
        if pr is not None:
            out["provider"] = pr.get("Name", "")
    ed = ev.find(EVT_NS + "EventData")
    if ed is not None:
        for d in ed.findall(EVT_NS + "Data"):
            name = d.get("Name")
            if name:
                out["data"][name] = (d.text or "").strip()
    return out


def parse_events_xml(text):
    """Parse the concatenated <Event> elements printed by `wevtutil qe ... /f:xml`."""
    text = decode_output(text)
    text = re.sub(r"<\?xml[^>]*\?>", "", text).strip()
    if not text:
        return []
    try:
        root = ET.fromstring("<Events>" + text + "</Events>")
        events = [_event_to_dict(e) for e in root.findall(EVT_NS + "Event")]
        events += [_event_to_dict(e) for e in root.findall("Event")]
        return events
    except ET.ParseError:
        pass
    events = []  # slow path: one bad event must not hide the others
    for m in _EVENT_RE.finditer(text):
        try:
            events.append(_event_to_dict(ET.fromstring(m.group(0))))
        except ET.ParseError:
            continue
    return events


def wfp_direction(value):
    """5152/5157 Direction: '%%14592' = inbound, '%%14593' = outbound (or already rendered)."""
    v = (value or "").strip().lower()
    if v in ("%%14592", "inbound"):
        return "in"
    if v in ("%%14593", "outbound"):
        return "out"
    return "?"


PROTO_NAMES = {"1": "ICMP", "6": "TCP", "17": "UDP", "58": "ICMPv6", "2": "IGMP"}


# ----------------------------------------------------------------------------- IP helpers
def clean_ip(ip):
    if not ip:
        return ""
    ip = ip.strip().strip("[]")
    if "%" in ip:
        ip = ip.split("%", 1)[0]
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return ""
    if a.version == 6 and a.ipv4_mapped:
        return str(a.ipv4_mapped)
    return str(a)


class NetSet:
    def __init__(self, cidrs):
        self.nets = []
        for c in cidrs or []:
            try:
                self.nets.append(ipaddress.ip_network(c.strip(), strict=False))
            except ValueError:
                pass

    def __contains__(self, ip):
        ip = clean_ip(ip)
        if not ip:
            return False
        a = ipaddress.ip_address(ip)
        return any(a.version == n.version and a in n for n in self.nets)


def is_multicast_or_broadcast(ip):
    ip = clean_ip(ip)
    if not ip:
        return False
    a = ipaddress.ip_address(ip)
    return a.is_multicast or ip == "255.255.255.255" or (a.version == 4 and ip.endswith(".255"))


# ----------------------------------------------------------------------------- pfirewall.log
DEFAULT_PF_FIELDS = ["date", "time", "action", "protocol", "src-ip", "dst-ip", "src-port", "dst-port",
                     "size", "tcpflags", "tcpsyn", "tcpack", "tcpwin", "icmptype", "icmpcode", "info", "path"]


class PfirewallParser:
    """Stateful because the '#Fields:' header defines the columns (Windows 11 adds 'pid')."""

    def __init__(self):
        self.fields = list(DEFAULT_PF_FIELDS)

    def feed(self, line):
        line = line.strip()
        if not line:
            return None
        if line.startswith("#"):
            if line.lower().startswith("#fields:"):
                self.fields = line.split(":", 1)[1].split()
            return None
        parts = line.split()
        if len(parts) < 8:
            return None
        rec = dict(zip(self.fields, parts))
        out = {
            "ts": parse_local(rec.get("date", ""), rec.get("time", "")),
            "action": rec.get("action", "").upper(),
            "proto": rec.get("protocol", "").upper(),
            "src": clean_ip(rec.get("src-ip", "")),
            "dst": clean_ip(rec.get("dst-ip", "")),
            "sport": _int(rec.get("src-port")),
            "dport": _int(rec.get("dst-port")),
            "path": rec.get("path", "-").upper(),
            "pid": _int(rec.get("pid")),
        }
        if out["ts"] is None or not out["src"]:
            return None
        return out


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------------------- port scan
class ScanDetector:
    """Flags a source IP that hits >= threshold distinct ports within window seconds."""

    def __init__(self, threshold=10, window=60, cooldown=600, max_ips=5000):
        self.threshold, self.window, self.cooldown, self.max_ips = threshold, window, cooldown, max_ips
        self.hits = collections.OrderedDict()   # ip -> deque[(ts, port)]
        self.last_alert = {}

    def add(self, ip, port, ts):
        if port is None or not ip:
            return None
        dq = self.hits.get(ip)
        if dq is None:
            dq = collections.deque(maxlen=4000)
            self.hits[ip] = dq
            if len(self.hits) > self.max_ips:
                old, _ = self.hits.popitem(last=False)
                self.last_alert.pop(old, None)
        else:
            self.hits.move_to_end(ip)
        dq.append((ts, port))
        while dq and dq[0][0] < ts - self.window:
            dq.popleft()
        ports = {p for _, p in dq}
        if len(ports) >= self.threshold:
            last = self.last_alert.get(ip)
            if last is None or ts - last >= self.cooldown:
                self.last_alert[ip] = ts
                return {"ip": ip, "ports": sorted(ports), "count": len(ports), "window": self.window}
        return None


class InboundStats:
    """Blocked inbound attempts aggregated per source IP (for the dashboard)."""

    def __init__(self, max_ips=2000):
        self.by_ip = collections.OrderedDict()
        self.max_ips = max_ips
        self.total = 0

    def add(self, ip, port, proto, ts):
        self.total += 1
        s = self.by_ip.get(ip)
        if s is None:
            s = {"ip": ip, "count": 0, "ports": collections.Counter(), "protos": collections.Counter(),
                 "first": ts, "last": ts, "scan": False}
            self.by_ip[ip] = s
            if len(self.by_ip) > self.max_ips:
                self.by_ip.popitem(last=False)
        else:
            self.by_ip.move_to_end(ip)
        s["count"] += 1
        if port is not None:
            s["ports"][port] += 1
        s["protos"][proto] += 1
        s["last"] = max(s["last"], ts)

    def top(self, n=25):
        rows = sorted(self.by_ip.values(), key=lambda s: (s["scan"], s["count"]), reverse=True)[:n]
        return [{"ip": s["ip"], "count": s["count"], "distinct_ports": len(s["ports"]),
                 "top_ports": [p for p, _ in s["ports"].most_common(6)],
                 "protos": dict(s["protos"]), "first": s["first"], "last": s["last"], "scan": s["scan"]}
                for s in rows]


# ----------------------------------------------------------------------------- netstat
def parse_netstat(text):
    """Parse `netstat -ano` into dicts: proto, local, lport, remote, rport, state, pid."""
    rows = []
    for line in decode_output(text).splitlines():
        parts = line.split()
        if len(parts) < 4 or parts[0].upper() not in ("TCP", "UDP"):
            continue
        proto = parts[0].upper()
        if proto == "TCP" and len(parts) >= 5:
            state, pid = parts[3], parts[4]
        elif proto == "UDP":
            state, pid = "", parts[-1]
        else:
            continue
        l_ip, l_port = _split_endpoint(parts[1])
        r_ip, r_port = _split_endpoint(parts[2])
        rows.append({"proto": proto, "local": l_ip, "lport": l_port, "remote": r_ip, "rport": r_port,
                     "state": state.upper(), "pid": _int(pid)})
    return rows


def _split_endpoint(ep):
    if ep.startswith("["):
        host, _, port = ep[1:].partition("]:")
    else:
        host, _, port = ep.rpartition(":")
    host = host.split("%")[0]
    return host, _int(port)


# ----------------------------------------------------------------------------- ipconfig / tracert
def parse_gateways(ipconfig_text):
    gws = []
    lines = decode_output(ipconfig_text).splitlines()
    for i, line in enumerate(lines):
        if "Default Gateway" in line or "Standardgateway" in line:
            cand = [line.split(":", 1)[1].strip() if ":" in line else ""]
            j = i + 1
            while j < len(lines) and lines[j].startswith(" " * 20) and ". ." not in lines[j]:
                cand.append(lines[j].strip())
                j += 1
            for c in cand:
                ip = clean_ip(c)
                if ip:
                    gws.append(ip)
    return sorted(set(gws))


_HOP_RE = re.compile(r"^\s*(\d+)\s+(.*)$")


def parse_tracert(text):
    hops = []
    for line in decode_output(text).splitlines():
        m = _HOP_RE.match(line)
        if not m:
            continue
        rest = m.group(2)
        times = re.findall(r"(<?\d+)\s*ms|\*", rest)
        ipm = re.findall(r"(\d{1,3}(?:\.\d{1,3}){3}|[0-9a-fA-F:]{3,})\s*$", rest.strip())
        ip = clean_ip(ipm[0]) if ipm else ""
        hops.append({"hop": int(m.group(1)), "ip": ip or "*", "times": [t or "*" for t in times][:3]})
    return hops
