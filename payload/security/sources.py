"""Log writer and incremental readers for the event logs and pfirewall.log."""
import json
import os
import threading
import time

import parsers
import winutil


def expand(p):
    return os.path.expandvars(p) if p else p


# ----------------------------------------------------------------------------- logging
class JsonlLog:
    def __init__(self, path, max_mb=20, keep=3):
        self.path, self.max_bytes, self.keep = path, int(max_mb * 1024 * 1024), keep
        self.lock = threading.Lock()
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def write(self, rtype, **fields):
        rec = {"ts": round(time.time(), 3), "local_time": parsers.fmt_local(time.time()), "type": rtype}
        rec.update(fields)
        line = json.dumps(rec, default=str, ensure_ascii=False)
        with self.lock:
            try:
                if os.path.exists(self.path) and os.path.getsize(self.path) > self.max_bytes:
                    for i in range(self.keep - 1, 0, -1):
                        src = "%s.%d" % (self.path, i)
                        if os.path.exists(src):
                            os.replace(src, "%s.%d" % (self.path, i + 1))
                    os.replace(self.path, self.path + ".1")
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except OSError:
                pass


# ----------------------------------------------------------------------------- sources
class EventLogTail:
    """Incremental reader for one event log channel using `wevtutil qe` and EventRecordID."""

    def __init__(self, channel, event_ids, max_per_poll=500, max_backlog=5000):
        self.channel, self.ids = channel, list(event_ids)
        self.max_per_poll, self.max_backlog = max_per_poll, max_backlog
        self.bookmark = None
        self.state, self.msg = "off", "not started"
        self.last_ok = None
        self.count = 0
        self.skipped = 0

    def _query(self, xpath, count, newest_first=False):
        args = ["wevtutil", "qe", self.channel, "/q:" + xpath, "/f:xml", "/c:%d" % count,
                "/rd:%s" % ("true" if newest_first else "false")]
        rc, out = winutil.run(args, timeout=20)
        text = parsers.decode_output(out)
        if rc != 0:
            low = text.lower()
            if "access is denied" in low:
                self.state, self.msg = "bad", "access denied (run as administrator)"
            elif "could not be found" in low or "channel" in low and "not" in low:
                self.state, self.msg = "bad", "log not found (is Sysmon installed?)"
            else:
                self.state, self.msg = "bad", "wevtutil error: " + text.strip()[:120]
            return None
        return parsers.parse_events_xml(text)

    def _init_bookmark(self):
        evs = self._query("*", 1, newest_first=True)
        if evs is None:
            return False
        self.bookmark = evs[0]["record_id"] if evs else 0
        return True

    def poll(self):
        if not winutil.IS_WIN:
            return []
        if self.bookmark is None and not self._init_bookmark():
            return []
        ids = " or ".join("EventID=%d" % i for i in self.ids)
        xp = "*[System[(%s) and EventRecordID>%d]]" % (ids, self.bookmark)
        evs = self._query(xp, self.max_per_poll)
        if evs is None:
            return []
        self.state, self.msg, self.last_ok = "ok", "reading (%d events so far)" % self.count, time.time()
        if evs:
            self.bookmark = max(e["record_id"] or 0 for e in evs)
            self.count += len(evs)
            if len(evs) >= self.max_per_poll:
                # far behind (e.g. a flood of packet drops): jump to the newest to stay light
                newest = self._query("*", 1, newest_first=True)
                if newest and newest[0]["record_id"] - self.bookmark > self.max_backlog:
                    self.skipped += newest[0]["record_id"] - self.bookmark
                    self.bookmark = newest[0]["record_id"]
        return evs


class FirewallLogTail:
    """Follows pfirewall.log from the end, coping with the .old rotation."""

    def __init__(self, path):
        self.path = path
        self.offset = None
        self.parser = parsers.PfirewallParser()
        self.state, self.msg = "off", "not started"
        self.lines = 0
        self.partial = ""

    def poll(self, max_bytes=2 * 1024 * 1024):
        try:
            size = os.path.getsize(self.path)
        except FileNotFoundError:
            self.state, self.msg = "warn", "pfirewall.log not found (is dropped-packet logging on?)"
            return []
        except PermissionError:
            self.state, self.msg = "bad", "access denied (run as administrator)"
            return []
        if self.offset is None:
            self.offset = size        # start at the end: we only care about new lines
            self._read_header()
        if size < self.offset:        # rotated to pfirewall.log.old
            self.offset, self.partial = 0, ""
        if size == self.offset:
            self.state, self.msg = "ok", "following (%d lines read)" % self.lines
            return []
        try:
            with open(self.path, "rb") as f:
                f.seek(self.offset)
                chunk = f.read(max_bytes)
                self.offset = f.tell()
        except PermissionError:
            self.state, self.msg = "bad", "access denied (run as administrator)"
            return []
        text = self.partial + chunk.decode("utf-8", errors="replace")
        lines = text.split("\n")
        self.partial = lines.pop() if not text.endswith("\n") else ""
        out = []
        for line in lines:
            rec = self.parser.feed(line)
            if rec:
                out.append(rec)
        self.lines += len(out)
        self.state, self.msg = "ok", "following (%d lines read)" % self.lines
        return out

    def _read_header(self):
        try:
            with open(self.path, "r", encoding="utf-8", errors="replace") as f:
                for _ in range(8):
                    line = f.readline()
                    if not line:
                        break
                    self.parser.feed(line)
        except OSError:
            pass

