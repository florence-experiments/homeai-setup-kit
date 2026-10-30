"""File-integrity check for HomeAI presets/settings against a PowerShell Export-Csv baseline.

Baseline made with e.g.:
  Get-FileHash <HomeAI folder>\\homeai\\data\\presets.json, <HomeAI folder>\\homeai\\data\\settings.json |
      Export-Csv <HomeAI folder>\\extras\\security\\state\\baseline-hashes.csv -NoTypeInformation
Columns used: Hash, Path (Algorithm is optional, SHA256 assumed). A '#TYPE ...' first line
(Windows PowerShell 5.1 default) and any BOM/UTF-16 encoding are handled.
Restores happen ONLY when you click a button; never automatically.
"""
import csv
import hashlib
import io
import os
import shutil
import time


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def norm(path):
    return os.path.normcase(os.path.normpath(path)).replace("/", "\\").lower()


def _read_text(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def read_baseline(path):
    """-> (dict norm_path -> HASH, had_type_line, original_rows)"""
    text = _read_text(path)
    lines = text.splitlines()
    had_type = bool(lines) and lines[0].startswith("#")
    body = "\n".join(l for l in lines if not l.startswith("#"))
    rows = list(csv.DictReader(io.StringIO(body)))
    out = {}
    for r in rows:
        h, p = (r.get("Hash") or "").strip(), (r.get("Path") or "").strip()
        if h and p:
            out[norm(p)] = h.upper()
    return out, had_type, rows


def write_baseline(path, rows, had_type):
    """Rewrite in the same shape Export-Csv produces (all fields quoted)."""
    fields = ["Algorithm", "Hash", "Path"]
    for r in rows:
        for k in r:
            if k not in fields and k is not None:
                fields.append(k)
    buf = io.StringIO()
    if had_type:
        buf.write("#TYPE Microsoft.PowerShell.Commands.FileHashInfo\r\n")
    w = csv.DictWriter(buf, fieldnames=fields, quoting=csv.QUOTE_ALL, lineterminator="\r\n", extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in fields})
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(buf.getvalue())
    os.replace(tmp, path)


class IntegrityMonitor:
    def __init__(self, baseline_csv, files, interval=10):
        self.baseline_csv = baseline_csv
        self.files = files              # [{"path":..., "good":...}]
        self.interval = interval
        self.last_check = 0
        self.status = {}                # norm path -> dict
        self.alerted = {}               # norm path -> hash we already alerted on
        self.baseline = {}
        self.baseline_error = ""
        self.baseline_mtime = None

    def _load_baseline(self):
        try:
            m = os.path.getmtime(self.baseline_csv)
        except OSError:
            self.baseline, self.baseline_error = {}, "baseline file not found: " + self.baseline_csv
            return
        if m != self.baseline_mtime:
            try:
                self.baseline, _, _ = read_baseline(self.baseline_csv)
                self.baseline_error = ""
            except Exception as e:
                self.baseline, self.baseline_error = {}, "baseline unreadable: %s" % e
            self.baseline_mtime = m

    def check(self, now=None, force=False):
        """Returns a list of new alert dicts (one per new bad state, not repeated every poll)."""
        now = now or time.time()
        if not force and now - self.last_check < self.interval:
            return []
        self.last_check = now
        self._load_baseline()
        alerts = []
        for f in self.files:
            p, key = f["path"], norm(f["path"])
            expected = self.baseline.get(key)
            st = {"path": p, "good": f.get("good", ""), "expected": expected or "", "checked": now,
                  "good_exists": bool(f.get("good")) and os.path.exists(f.get("good", ""))}
            if not os.path.exists(p):
                st.update(state="MISSING", actual="")
            else:
                try:
                    st["actual"] = sha256_file(p)
                except OSError as e:
                    st.update(state="UNREADABLE", actual="", error=str(e))
                else:
                    if not expected:
                        st["state"] = "NO_BASELINE"
                    elif st["actual"] == expected:
                        st["state"] = "OK"
                    else:
                        st["state"] = "CHANGED"
            self.status[key] = st
            if st["state"] in ("CHANGED", "MISSING"):
                marker = st["state"] + ":" + st.get("actual", "")
                if self.alerted.get(key) != marker:
                    self.alerted[key] = marker
                    alerts.append(dict(st))
            else:
                self.alerted.pop(key, None)
        return alerts

    def restore(self, path):
        """Copy the .good file over the live file (after a click). Keeps a copy of the changed file."""
        f = next((x for x in self.files if norm(x["path"]) == norm(path)), None)
        if not f or not f.get("good"):
            return False, "no good copy configured for " + path
        good = f["good"]
        if not os.path.exists(good):
            return False, "good copy not found: " + good
        expected = self.baseline.get(norm(path))
        good_hash = sha256_file(good)
        if os.path.exists(path):
            keep = "%s.changed-%s" % (path, time.strftime("%Y%m%d-%H%M%S"))
            shutil.copy2(path, keep)
        shutil.copy2(good, path)
        self.check(force=True)
        if expected and good_hash != expected:
            return True, "restored, but the good copy does not match the baseline hash (baseline may be stale)"
        return True, "restored from " + good

    def accept(self, path):
        """'This change was me': new baseline hash + refresh the good copy (old one kept as .bak)."""
        f = next((x for x in self.files if norm(x["path"]) == norm(path)), None)
        if not f or not os.path.exists(path):
            return False, "file not found"
        new_hash = sha256_file(path)
        if os.path.exists(self.baseline_csv):
            _, had_type, rows = read_baseline(self.baseline_csv)
        else:
            had_type, rows = False, []
        for r in rows:
            if norm(r.get("Path", "")) == norm(path):
                r["Hash"], r["Algorithm"] = new_hash, r.get("Algorithm") or "SHA256"
                break
        else:
            rows.append({"Algorithm": "SHA256", "Hash": new_hash, "Path": path})
        write_baseline(self.baseline_csv, rows, had_type)
        good = f.get("good")
        if good:
            if os.path.exists(good):
                shutil.copy2(good, good + ".bak-" + time.strftime("%Y%m%d-%H%M%S"))
            shutil.copy2(path, good)
        self.baseline_mtime = None
        self.check(force=True)
        return True, "baseline updated"

    def snapshot(self):
        return {"baseline_csv": self.baseline_csv, "baseline_error": self.baseline_error,
                "files": list(self.status.values())}
