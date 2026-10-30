"""Big, always-on-top alert window (tkinter ships with Python). Runs on the main thread;
other threads hand alerts over through a queue."""
import queue
import threading
import webbrowser

import parsers
import winutil

try:
    import tkinter as tk
    from tkinter import messagebox
    HAVE_TK = True
except Exception:          # tkinter missing (e.g. an embeddable Python): use a plain message box
    HAVE_TK = False

RED, DARK, FG, MUTED = "#c62828", "#14161a", "#e8eaed", "#9aa0a6"


def alert_lines(a):
    e = a.get("enrichment", {})
    geo = e.get("geo", {}) or {}
    rows = [
        ("Time", parsers.fmt_local(a.get("time"))),
        ("What", a.get("title", "")),
        ("Program", a.get("image", "")),
        ("Process ID", a.get("pid") or ""),
        ("Remote IP", ("%s:%s" % (a.get("remote_ip"), a.get("remote_port") or "")).strip(":") if a.get("remote_ip") else ""),
        ("Direction", {"out": "outgoing", "in": "incoming"}.get(a.get("direction"), a.get("direction", ""))),
        ("Scope", e.get("scope", "")),
        ("Location", ", ".join(x for x in (geo.get("city"), geo.get("region"), geo.get("country")) if x)),
        ("Network", geo.get("network", "")),
        ("Host name", e.get("reverse_dns", "")),
        ("Names seen", ", ".join(e.get("dns_names_seen", []))),
        ("Action", a.get("action", "")),
    ]
    og = e.get("online_geo")
    if og and not og.get("error"):
        rows.append(("Online geo", "%s, %s (%s)" % (og.get("city", ""), og.get("country", ""), og.get("isp", ""))))
    for k, v in (a.get("details") or {}).items():
        if isinstance(v, list):
            v = ", ".join(str(x) for x in v[:30])
        rows.append((k.replace("_", " ").capitalize(), v))
    tr = e.get("traceroute")
    if tr:
        if tr.get("hops"):
            rows.append(("Route", "  >  ".join(h["ip"] for h in tr["hops"])))
        elif tr.get("status") == "running":
            rows.append(("Route", "traceroute running..."))
    return [(k, str(v)) for k, v in rows if v not in ("", None)]


class PopupManager:
    def __init__(self, engine, enabled=True):
        self.engine = engine
        self.q = queue.Queue()
        self.enabled = enabled
        self.root = None
        self.open = 0

    # called from any thread
    def show(self, alert):
        if self.enabled:
            self.q.put(alert)

    def run_forever(self, stop_event):
        """Blocks the calling (main) thread until stop_event is set."""
        if not (HAVE_TK and self.enabled):
            while not stop_event.wait(0.5):
                self._drain_fallback()
            return
        try:
            self.root = tk.Tk()
        except Exception:      # no desktop available: fall back to a plain message box
            self.root = None
            while not stop_event.wait(0.5):
                self._drain_fallback()
            return
        self.root.withdraw()

        def tick():
            if stop_event.is_set():
                self.root.quit()
                return
            try:
                while True:
                    self._open_window(self.q.get_nowait())
            except queue.Empty:
                pass
            self.root.after(300, tick)
        self.root.after(300, tick)
        self.root.mainloop()

    def _drain_fallback(self):
        try:
            a = self.q.get_nowait()
        except queue.Empty:
            return
        text = "\n".join("%s: %s" % kv for kv in alert_lines(a))
        threading.Thread(target=winutil.message_box, args=("SECURITY ALERT", text), daemon=True).start()

    def _open_window(self, a):
        maxo = self.engine.cfg.get("alerts", {}).get("max_open_popups", 4)
        if self.open >= maxo:
            self.engine.note("popup suppressed (too many open)", alert_id=a.get("id"))
            return
        self.open += 1
        w = tk.Toplevel(self.root)
        w.title("Security alert")
        w.configure(bg=DARK)
        w.attributes("-topmost", True)
        w.geometry("700x560+%d+%d" % (120 + 30 * self.open, 80 + 30 * self.open))
        hdr = tk.Frame(w, bg=RED)
        hdr.pack(fill="x")
        tk.Label(hdr, text="\u26a0  SECURITY ALERT" + ("  (TEST)" if a.get("test") else ""), bg=RED, fg="white",
                 font=("Segoe UI", 24, "bold"), pady=10).pack()
        tk.Label(hdr, text=a.get("title", ""), bg=RED, fg="white", font=("Segoe UI", 13), wraplength=660,
                 pady=4).pack()
        body = tk.Text(w, bg=DARK, fg=FG, font=("Consolas", 10), relief="flat", wrap="word", padx=12, pady=10)
        body.tag_configure("k", foreground=MUTED)
        body.pack(fill="both", expand=True)

        def fill():
            if not w.winfo_exists():
                return
            body.configure(state="normal")
            body.delete("1.0", "end")
            for k, v in alert_lines(a):
                body.insert("end", "%-12s " % k, "k")
                body.insert("end", v + "\n")
            body.configure(state="disabled")
            if not a.get("enrichment", {}).get("complete") and a.get("remote_ip") and not a.get("test"):
                w.after(1500, fill)
        fill()
        self._buttons(w, a)
        if self.engine.cfg.get("alerts", {}).get("sound", True):
            try:
                w.bell()
            except Exception:
                pass
        w.lift()
        w.focus_force()

    def _buttons(self, w, a):
        btns = tk.Frame(w, bg=DARK, pady=8)
        btns.pack(fill="x")

        def close():
            self.open = max(0, self.open - 1)
            w.destroy()

        def do(action, question):
            if question and not messagebox.askyesno("Please confirm", question, parent=w):
                return
            ok, msg = self.engine.action(action, a.get("id"))
            messagebox.showinfo("Security Watcher", msg, parent=w)
            if ok:
                close()

        def mk(text, cmd, enabled=True, color="#2d333b"):
            b = tk.Button(btns, text=text, command=cmd, font=("Segoe UI", 11, "bold"), bg=color, fg="white",
                          activebackground="#444c56", relief="flat", padx=14, pady=6,
                          state=("normal" if enabled else "disabled"))
            b.pack(side="left", padx=6)

        tamper = a.get("kind") == "file_tamper"
        target = (a.get("details") or {}).get("file", "")
        mk("Dismiss", close)
        mk("Allow this app",
           lambda: do("allow_app", "Allow %s from now on?\n\nThe watcher will stop alerting on and closing this "
                                   "program. Windows Firewall rules are not changed." % a.get("image", "")),
           enabled=bool(a.get("image")) and not a.get("test"))
        mk("Restore file",
           lambda: do("restore", "Replace %s with the saved good copy?\n\nThe changed file is kept next to it "
                                 "as .changed-<time>." % target),
           enabled=tamper, color="#1f6feb")
        if tamper:
            mk("This change was me", lambda: do("accept", "Accept the current file as the new good version?"))
        if a.get("kind") == "port_scan" and a.get("can_block"):
            mk("Block this IP", lambda: do("block_ip", "Add a Windows Firewall rule blocking %s?" % a.get("remote_ip")))
        mk("Open Monitor", lambda: webbrowser.open("http://127.0.0.1:%s/" % self.engine.port))
        w.protocol("WM_DELETE_WINDOW", close)
