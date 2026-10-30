"""Engine part: closing (killing) unapproved AI processes safely."""
import ntpath
import time

import parsers
import winutil


class ClosingMixin:
    # ------------------------------------------------------------------ closing processes
    def closing_paused(self):
        return time.time() < self.kill_paused_until

    def _maybe_kill(self, f, a):
        acts = self.cfg.get("actions", {})
        pid, image = f.get("pid"), f.get("image") or ""
        now = time.time()

        def done(text, **kw):
            a["action"] = text
            self.log.write("action", alert_id=a["id"], action=text, pid=pid, image=image, **kw)

        if self.closing_paused():
            return done("NOT closed: auto-close is paused until " + parsers.fmt_local(self.kill_paused_until)[11:16])
        if not pid or pid in (0, 4, self.own_pid, self.parent_pid):
            return done("NOT closed: no usable process id")
        if self.rules.is_never_kill(image) or self.rules.is_allowed(image):
            return done("alert only (protected app)")
        et = f.get("event_time")
        if et and now - et > acts.get("max_event_age_seconds", 30):
            return done("NOT closed: event is %ds old (process id may be reused)" % (now - et))
        current = winutil.process_image(pid)
        if not current:
            return done("process had already exited")
        if ntpath.basename(current).lower() != ntpath.basename(image).lower():
            return done("NOT closed: process id now belongs to " + ntpath.basename(current))
        if self.rules.is_never_kill(current):
            return done("alert only (protected app)")
        targets = []
        if acts.get("kill_process_tree", True):
            procs = winutil.list_processes()
            for c in winutil.descendants(pid, procs):
                if c in (self.own_pid, self.parent_pid, 0, 4):
                    continue
                cimg = winutil.process_image(c) or (procs.get(c, (0, ""))[1])
                if self.rules.is_never_kill(cimg) or self.rules.is_allowed(cimg):
                    continue
                targets.append((c, cimg))
        targets.append((pid, current))
        images = dict(targets)
        results = [{"pid": p, "image": images.get(p, ""), "ok": ok, "msg": m[:200]}
                   for p, ok, m in winutil.kill_many([t[0] for t in targets])]
        main_ok = results[-1]["ok"] if results else False
        n_child = sum(1 for r in results[:-1] if r["ok"])
        name = ntpath.basename(current)
        if main_ok:
            text = "CLOSED %s (pid %s)" % (name, pid)
        else:
            text = "FAILED to close %s (pid %s): %s" % (name, pid, results[-1]["msg"])
        if n_child:
            text += " + %d child process%s" % (n_child, "es" if n_child > 1 else "")
        self.counters["closed" if main_ok else "close_failed"] += 1
        done(text, results=results)
