"""'+ Add mode' for the HomeAI server: search Hugging Face in a background job, then download the chosen model
(only after the user typed yes in the dialog), wire it into models.ini / presets / routing and ask llama-server
to re-read its model list. Uses the setup kit installed next to HomeAI (../kit)."""
import http.client
import os
import sys
import threading
import time
import urllib.parse
import uuid

JOBS = {}
LOCK = threading.Lock()
MAX_JOBS = 20


def _kit(cfg):
    kd = cfg.get("kit_dir")
    if not kd or not os.path.isdir(os.path.join(kd, "homeai_setup")):
        raise RuntimeError("the HomeAI setup kit was not found next to HomeAI (expected %s)" % kd)
    if kd not in sys.path:
        sys.path.insert(0, kd)
    from homeai_setup import addmode, configgen, modes, util  # noqa
    return addmode, configgen, modes, util


class Job:
    def __init__(self, kind, mode):
        self.id = uuid.uuid4().hex[:12]
        self.kind, self.mode = kind, mode
        self.state, self.log, self.result, self.error = "running", [], None, None
        self.token = None
        self.files = []          # (final path, size) for progress
        self.t = time.time()

    def say(self, *a):
        self.log.append(" ".join(str(x) for x in a))
        del self.log[:-200]

    def view(self):
        done = total = 0
        for path, size in self.files:
            total += size or 0
            for p in (path, path + ".part"):
                try:
                    done += os.path.getsize(p)
                    break
                except OSError:
                    pass
        out = {"id": self.id, "kind": self.kind, "mode": self.mode, "state": self.state, "log": self.log[-30:],
               "error": self.error, "result": self.result}
        if total:
            out["progress"] = {"done": min(done, total), "total": total}
        return out


def _start(job, fn):
    with LOCK:
        if len(JOBS) >= MAX_JOBS:
            for k in sorted(JOBS, key=lambda k: JOBS[k].t)[: len(JOBS) - MAX_JOBS + 1]:
                if JOBS[k].state != "running":
                    JOBS.pop(k, None)
        JOBS[job.id] = job

    def run():
        try:
            job.result = fn()
            job.state = "done"
        except Exception as e:  # noqa
            job.state, job.error = "error", "%s" % e
            job.say("Error: %s" % e)
        finally:
            job.token = None     # the token only lives for the job
    threading.Thread(target=run, daemon=True).start()
    return job


def _reload_llama(cfg):
    try:
        u = urllib.parse.urlsplit(cfg["llama_url"])
        c = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=10)
        c.request("GET", (u.path.rstrip("/") or "") + "/models?reload=1")
        c.getresponse().read()
        c.close()
        return True
    except Exception:
        return False


def installed_js(cfg):
    import json
    p = os.path.join(cfg["data_dir"], "installed.json")
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {"profiles": [], "modes": []}
    return ("window.HOMEAI_INSTALLED = %s;\n" % json.dumps(data)).encode("utf-8")


def handle(h, method, path, cfg):
    """Returns True when the request was handled. h = the HTTP handler (send_json, send_error_json, read_json_body)."""
    if path == "/installed.js" and method in ("GET", "HEAD"):
        data = installed_js(cfg)
        h.send_response(200)
        h.send_header("Content-Type", "application/javascript; charset=utf-8")
        h.send_header("Content-Length", str(len(data)))
        h.send_header("Cache-Control", "no-cache")
        h.end_headers()
        if method == "GET":
            h.wfile.write(data)
        return True
    if not path.startswith("/api/modes"):
        return False
    try:
        addmode, configgen, modes, util = _kit(cfg)
    except Exception as e:  # noqa
        h.send_error_json(503, str(e))
        return True
    root = cfg["install_root"]
    if path == "/api/modes" and method == "GET":
        st = configgen.load_state(root) or {"modes": {}}
        busy = any(j.state == "running" and j.kind == "add" for j in JOBS.values())
        h.send_json({"catalog": modes.catalog(), "installed": sorted(st.get("modes", {})), "busy": busy,
                     "models": sorted(st.get("models", {}))})
        return True
    if path == "/api/modes/search" and method == "POST":
        req = h.read_json_body()
        mode = str(req.get("mode") or "")
        if mode not in modes.MODES:
            h.send_error_json(400, "unknown mode")
            return True
        job = Job("search", mode)
        job.token = (str(req.get("hf_token") or "").strip() or None)
        tok = job.token
        _start(job, lambda: addmode.search_mode(root, mode, tok, job.say))
        h.send_json(job.view())
        return True
    if path.startswith("/api/modes/jobs/") and method == "GET":
        job = JOBS.get(path.rsplit("/", 1)[-1])
        if not job:
            h.send_error_json(404, "no such job")
        else:
            h.send_json(job.view())
        return True
    if path == "/api/modes/add" and method == "POST":
        req = h.read_json_body()
        sj = JOBS.get(str(req.get("job_id") or ""))
        if not sj or sj.kind != "search" or sj.state != "done":
            h.send_error_json(400, "run a search first")
            return True
        if any(j.state == "running" and j.kind == "add" for j in JOBS.values()):
            h.send_error_json(409, "another mode is being added - wait for it to finish")
            return True
        pick = req.get("pick")
        res = sj.result or {}
        if isinstance(pick, str) and pick.startswith("existing:"):
            sec = pick.split(":", 1)[1]
            if sec not in [e["section"] for e in res.get("existing", [])]:
                h.send_error_json(400, "unknown model")
                return True
            choice = {"existing": sec}
        else:
            try:
                choice = res["choices"][int(pick)]
            except (KeyError, IndexError, TypeError, ValueError):
                h.send_error_json(400, "pick one of the suggestions")
                return True
            if not util.is_yes(str(req.get("confirm") or "")):
                h.send_error_json(400, "type yes to confirm the download")
                return True
        job = Job("add", sj.mode)
        tok = (str(req.get("hf_token") or "").strip() or None)
        if not choice.get("existing"):
            d = configgen.model_dir(root, choice["repo"])
            items = list(choice["files"]) + ([choice["mmproj"]] if choice.get("mmproj") and modes.MODES[sj.mode].get("vision") else [])
            job.files = [(os.path.join(d, f["path"].rsplit("/", 1)[-1]), f.get("size") or 0) for f in items]

        def work():
            sec = addmode.apply(root, sj.mode, dict(choice), tok, job.say)
            ok = _reload_llama(cfg)
            job.say("AI engine model list reloaded." if ok else "Start (or restart) the AI engine to use the new model.")
            return {"section": sec, "mode": sj.mode}
        _start(job, work)
        h.send_json(job.view())
        return True
    h.send_error_json(404, "not found")
    return True
