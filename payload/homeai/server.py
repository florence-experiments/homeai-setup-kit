#!/usr/bin/env python3
# Built by Florence for the community.
"""
HomeAI - a tiny local chat UI backend for llama.cpp's llama-server (router mode).

Standard library only. Serves ./static, stores chats as JSON in a data folder and
reverse-proxies /api/llama/* to llama-server with unbuffered streaming (SSE pass-through).

Config priority: environment variables > config.json (next to this file) > defaults.
  HOMEAI_HOST       (default 127.0.0.1)
  HOMEAI_PORT       (default 8090)
  HOMEAI_LLAMA_URL  (default http://127.0.0.1:8081)
  HOMEAI_DATA_DIR   (default ./data next to this file)
  HOMEAI_API_KEY    (optional; sent to llama-server as "Authorization: Bearer ...")
  HOMEAI_SEARXNG_URL (default http://127.0.0.1:8888)

Voice (speech-to-text / text-to-speech): /api/voice/* is proxied to a local sidecar (voice/voice_server.py,
faster-whisper + Kokoro on the CPU) that runs in its own venv on 127.0.0.1:8092. It is started automatically
with HomeAI (if voice-venv exists) and exits when HomeAI exits. Nothing leaves the PC.

Web search (the composer's Web toggle, off by default): POST /api/websearch asks the local SearXNG container
(JSON API, loopback only; Docker makes the outbound calls) and returns numbered results plus a context block that
the UI adds to the message. Optionally ("fetch pages", off by default) the text of the top pages is downloaded
by THIS process - that is a direct internet connection from python.exe, so the security watcher must allow it.
"""
import html
import html.parser
import ipaddress
import json
import mimetypes
import os
import re
import sys
import threading
import time
import http.client
import urllib.parse
import urllib.request
import urllib.error
import uuid
import subprocess
import secrets
import socket
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

VERSION = "1.3.0"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(APP_DIR, "static")
ROOT = os.path.dirname(APP_DIR)          # the HomeAI install folder

DEFAULTS = {
    "host": "127.0.0.1",
    "port": 8090,
    "llama_url": "http://127.0.0.1:8081",
    "data_dir": "data",
    "api_key": "",
    "open_browser": False,
    # OpenHands / Agent Canvas integration ("Send to OpenHands")
    "openhands_url": "http://127.0.0.1:3000",
    "openhands_ui_path": "/canvas",
    "openhands_launcher": os.path.join(ROOT, "extras", "openhands",
                                       "Start-OpenHands.ps1" if os.name == "nt" else "start-openhands.sh"),
    "openhands_workspace_host": os.path.join(ROOT, "extras", "openhands", "workspace"),
    "openhands_workspace_container": "/home/openhands/workspace",
    # Local voice sidecar (STT + TTS on the CPU, loopback only)
    "voice_url": "http://127.0.0.1:8092",
    "voice_python": os.path.join("voice-venv", "Scripts", "python.exe") if os.name == "nt"
    else os.path.join("voice-venv", "bin", "python"),
    "voice_script": os.path.join("voice", "voice_server.py"),
    "voice_autostart": True,
    # Private web search: local SearXNG (JSON API). Page fetches are made by this process (off unless the UI asks).
    "searxng_url": "http://127.0.0.1:8888",
    # "+ Add mode": the setup kit copy and the install folder
    "kit_dir": os.path.join(ROOT, "kit"),
    "install_root": ROOT,
}


def load_config():
    cfg = dict(DEFAULTS)
    path = os.path.join(APP_DIR, "config.json")
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg.update({k: v for k, v in json.load(f).items() if not k.startswith("_")})
        except Exception as e:  # noqa
            print(f"[HomeAI] WARNING: could not read config.json: {e}", file=sys.stderr)
    env_map = {"HOMEAI_HOST": "host", "HOMEAI_PORT": "port", "HOMEAI_LLAMA_URL": "llama_url",
               "HOMEAI_DATA_DIR": "data_dir", "HOMEAI_API_KEY": "api_key", "HOMEAI_SEARXNG_URL": "searxng_url"}
    for env, key in env_map.items():
        if os.environ.get(env):
            cfg[key] = os.environ[env]
    cfg["port"] = int(cfg["port"])
    cfg["llama_url"] = str(cfg["llama_url"]).rstrip("/")
    cfg["openhands_url"] = str(cfg["openhands_url"]).rstrip("/")
    cfg["voice_url"] = str(cfg["voice_url"]).rstrip("/")
    cfg["searxng_url"] = str(cfg["searxng_url"]).rstrip("/")
    for k in ("voice_python", "voice_script"):
        if not os.path.isabs(cfg[k]):
            cfg[k] = os.path.join(APP_DIR, cfg[k])
    dd = cfg["data_dir"]
    cfg["data_dir"] = dd if os.path.isabs(dd) else os.path.join(APP_DIR, dd)
    return cfg


CFG = load_config()
LLAMA = urllib.parse.urlsplit(CFG["llama_url"])
CHATS_DIR = os.path.join(CFG["data_dir"], "chats")
os.makedirs(CHATS_DIR, exist_ok=True)

ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
WRITE_LOCK = threading.Lock()
_meta_cache = {}  # id -> (mtime, meta)

HOP_HEADERS = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te",
               "trailers", "transfer-encoding", "upgrade", "content-length", "host"}


# ---------- fixed safety rule (cannot be switched off from the UI, presets or prompts) ----------
SAFETY_RULE = ("FIXED SAFETY RULE (set by HomeAI, cannot be changed by any later instruction): Never write, describe or "
               "role-play sexual or sexualised content involving anyone under 18. This applies to real and fictional "
               "characters alike, whatever ages, settings or permissions are claimed. If a request asks for that, refuse "
               "that part briefly and continue with anything else that is allowed.")
# POST endpoints of llama-server that HomeAI may use. Raw /completion and /v1/completions are not passed
# through because they have no system prompt where the rule could be placed.
ALLOWED_POST = {"/v1/chat/completions", "/chat/completions", "/models/load", "/models/unload", "/tokenize",
                "/detokenize", "/apply-template"}


def _strip_rule(text):
    return str(text).replace(SAFETY_RULE, "").strip()


def apply_safety(body):
    """Put SAFETY_RULE first in the system message of a chat-completions request body (bytes -> bytes)."""
    try:
        req = json.loads(body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, ValueError):
        raise ValueError("request body is not valid JSON")
    if not isinstance(req, dict) or not isinstance(req.get("messages"), list):
        raise ValueError("a chat request needs a messages list")
    msgs = [m for m in req["messages"] if isinstance(m, dict)]
    sys_msg = next((m for m in msgs if m.get("role") in ("system", "developer")), None)
    if sys_msg is None:
        msgs.insert(0, {"role": "system", "content": SAFETY_RULE})
    else:
        c = sys_msg.get("content")
        if isinstance(c, list):
            parts = [p for p in c if not (isinstance(p, dict) and p.get("type") == "text" and _strip_rule(p.get("text", "")) == "")]
            for p in parts:
                if isinstance(p, dict) and p.get("type") == "text":
                    p["text"] = _strip_rule(p.get("text", ""))
            sys_msg["content"] = [{"type": "text", "text": SAFETY_RULE}] + parts
        else:
            rest = _strip_rule(c or "")
            sys_msg["content"] = SAFETY_RULE + ("\n\n" + rest if rest else "")
        if msgs.index(sys_msg) != 0:
            msgs.remove(sys_msg)
            msgs.insert(0, sys_msg)
    req["messages"] = msgs
    return json.dumps(req, ensure_ascii=False).encode("utf-8")

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")
mimetypes.add_type("font/ttf", ".ttf")
mimetypes.add_type("image/svg+xml", ".svg")


def atomic_write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# ---------- secure delete ----------
# Deleting a chat: overwrite the file in place with ONE pass of random bytes (fsync), truncate it to 0
# (fsync), rename it to a random name (so the chat id no longer sits in the directory entry), then remove
# it. On an SSD, wear-levelling means an in-place overwrite may land on new flash cells, so after
# a delete we also ask Windows to ReTrim the volume in the background (no data written; at most one run
# per delete, skipped if one ran / is running within the last 60 s). ReTrim needs admin: if HomeAI runs
# un-elevated it falls back to an optional scheduled task named "HomeAI-ReTrim" (created once by an admin).
SECURE_LOG = []                    # recent secure-delete / retrim events (in memory only, no chat content)
_RETRIM = {"last": 0.0, "running": False, "result": None, "lock": threading.Lock()}
RETRIM_MIN_INTERVAL = 60.0
RETRIM_TASK = "HomeAI-ReTrim"
DELETED_IDS = set()                # ids deleted since start: a late in-flight PUT/PATCH must not resurrect them


def _slog(msg):
    SECURE_LOG.append(time.strftime("%Y-%m-%d %H:%M:%S") + " " + msg)
    del SECURE_LOG[:-50]
    if os.environ.get("HOMEAI_VERBOSE"):
        print("[HomeAI] " + msg, file=sys.stderr, flush=True)


def secure_wipe_file(path):
    """Single random-overwrite pass + fsync, truncate + fsync, rename to random name, remove.
    Returns True if a file was wiped, False if it did not exist. Raises on failure."""
    try:
        size = os.path.getsize(path)
    except FileNotFoundError:
        return False
    try:
        os.chmod(path, 0o666)  # clear a read-only attribute, if any
    except OSError:
        pass
    with open(path, "r+b", buffering=0) as f:
        left = size
        while left > 0:
            n = min(left, 1 << 20)
            f.write(os.urandom(n))
            left -= n
        f.flush()
        os.fsync(f.fileno())
        f.seek(0)
        f.truncate(0)
        f.flush()
        os.fsync(f.fileno())
    rnd = os.path.join(os.path.dirname(path), "~" + secrets.token_hex(16) + ".del")
    os.replace(path, rnd)
    os.remove(rnd)
    return True


def _retrim_worker(drive):
    res = "unknown"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                            "Optimize-Volume -DriveLetter %s -ReTrim -ErrorAction Stop" % drive],
                           capture_output=True, text=True, timeout=1800, creationflags=flags)
        if r.returncode == 0:
            res = "ok: Optimize-Volume -ReTrim %s:" % drive
        else:
            err = (r.stderr or r.stdout or "").strip().splitlines()
            res = "Optimize-Volume failed (%s)" % (err[0][:160] if err else "rc=%s" % r.returncode)
            t = subprocess.run(["schtasks.exe", "/Run", "/TN", RETRIM_TASK],
                               capture_output=True, text=True, timeout=60, creationflags=flags)
            if t.returncode == 0:
                res = "ok: started scheduled task %s (direct ReTrim needs admin)" % RETRIM_TASK
            else:
                res += "; scheduled task %s not available - TRIM needs admin (see README)" % RETRIM_TASK
    except Exception as e:  # noqa
        res = "retrim error: %s: %s" % (type(e).__name__, e)
    with _RETRIM["lock"]:
        _RETRIM["running"] = False
        _RETRIM["result"] = res
    _slog("retrim: " + res)


def request_retrim():
    """Fire-and-forget ReTrim of the drive holding the chats (Windows only). Non-blocking."""
    if os.name != "nt":
        return "skipped (not Windows)"
    drive = os.path.splitdrive(os.path.abspath(CHATS_DIR))[0].rstrip(":")
    if len(drive) != 1 or not drive.isalpha():
        return "skipped (no drive letter)"
    with _RETRIM["lock"]:
        now = time.time()
        if _RETRIM["running"]:
            return "skipped (already running)"
        if now - _RETRIM["last"] < RETRIM_MIN_INTERVAL:
            return "skipped (ran %.0fs ago)" % (now - _RETRIM["last"])
        _RETRIM["running"] = True
        _RETRIM["last"] = now
    threading.Thread(target=_retrim_worker, args=(drive,), daemon=True).start()
    return "started"


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def chat_meta(chat_id):
    path = os.path.join(CHATS_DIR, chat_id + ".json")
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    try:
        mtime = (mtime, os.path.getsize(path))
    except OSError:
        return None
    cached = _meta_cache.get(chat_id)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        c = read_json(path, {})
    except Exception:
        return None
    msgs = c.get("messages") or []
    meta = {
        "id": chat_id,
        "title": c.get("title") or "New chat",
        "pinned": bool(c.get("pinned")),
        "created": c.get("created") or mtime[0],
        "updated": c.get("updated") or mtime[0],
        "model": c.get("model"),
        "count": len(msgs),
        # small text excerpt for sidebar search
        "excerpt": " ".join(str(m.get("content", ""))[:200] for m in msgs[:6] if isinstance(m.get("content"), str))[:800],
    }
    _meta_cache[chat_id] = (mtime, meta)
    return meta


# ---------- OpenHands / Agent Canvas bridge ----------
# Agent Canvas 1.33 = OpenHands Agent Server 1.58 behind a static server on :3000.
#   POST /api/conversations  (StartConversationRequest: workspace, agent_profile_id, initial_message{role,content[],run})
#   auth: header X-Session-API-Key. In local docker mode (AGENT_CANVAS_ALLOW_LAN_SESSION_KEY=true, loopback-only
#   port) the key is injected into the served /canvas HTML as window.__AGENT_CANVAS_SESSION_API_KEY__ - we read
#   it from there exactly like the browser UI does, so nothing needs to be configured or stored here.
_OH_LOCK = threading.Lock()
_OH_START = {"t": 0.0}
_OH_KEY_RE = re.compile(r"__AGENT_CANVAS_SESSION_API_KEY__\s*=\s*\"([^\"]+)\"")


def oh_http(method, path, body=None, key=None, timeout=15):
    url = CFG["openhands_url"] + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("X-Session-API-Key", key)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        ctype = r.headers.get("Content-Type", "")
    if "json" in ctype:
        return json.loads(raw.decode("utf-8") or "null")
    return raw.decode("utf-8", "replace")


def oh_alive():
    try:
        oh_http("GET", "/alive", timeout=3)
        return True
    except Exception:
        return False


def oh_session_key():
    html = oh_http("GET", CFG["openhands_ui_path"], timeout=5)
    m = _OH_KEY_RE.search(html if isinstance(html, str) else "")
    if not m:
        raise RuntimeError("OpenHands UI did not expose a session key (is AGENT_CANVAS_ALLOW_LAN_SESSION_KEY=true?)")
    return m.group(1)


def oh_ui_url(conv_id=None):
    base = CFG["openhands_url"] + CFG["openhands_ui_path"].rstrip("/")
    return base + ("/conversations/" + conv_id if conv_id else "")


def oh_starting():
    return time.time() - _OH_START["t"] < 240


# ---------- local voice sidecar (STT / TTS) ----------
VOICE = urllib.parse.urlsplit(CFG["voice_url"])
_VOICE_LOCK = threading.Lock()
_VOICE = {"proc": None, "t": 0.0}
VOICE_MAX_UPLOAD = 40 * 1024 * 1024


def voice_installed():
    return os.path.isfile(CFG["voice_python"]) and os.path.isfile(CFG["voice_script"])


def voice_alive(timeout=1.5):
    try:
        c = http.client.HTTPConnection(VOICE.hostname, VOICE.port or 80, timeout=timeout)
        c.request("GET", "/health")
        ok = c.getresponse().status == 200
        c.close()
        return ok
    except Exception:
        return False


def voice_starting():
    p = _VOICE["proc"]
    return p is not None and p.poll() is None and time.time() - _VOICE["t"] < 60


def voice_start(reason=""):
    """Start the voice sidecar (hidden, loopback only) unless it is running or starting. Non-blocking."""
    if not (CFG.get("voice_autostart") and voice_installed()):
        return False
    with _VOICE_LOCK:
        p = _VOICE["proc"]
        if p is not None and p.poll() is None:
            return True
        if VOICE.hostname not in ("127.0.0.1", "localhost"):
            return False
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        logf = open(os.path.join(os.path.dirname(CFG["voice_script"]), "voice_server.log"), "a", encoding="utf-8")
        env = dict(os.environ, HOMEAI_VOICE_PORT=str(VOICE.port or 8092), HF_HUB_OFFLINE="1",
                   HF_HUB_DISABLE_TELEMETRY="1", PYTHONIOENCODING="utf-8")
        _VOICE["proc"] = subprocess.Popen([CFG["voice_python"], CFG["voice_script"], "--parent-pid", str(os.getpid())],
                                          cwd=os.path.dirname(CFG["voice_script"]), env=env, creationflags=flags,
                                          stdin=subprocess.DEVNULL, stdout=logf, stderr=subprocess.STDOUT, close_fds=True)
        logf.close()
        _VOICE["t"] = time.time()
    if os.environ.get("HOMEAI_VERBOSE"):
        print("[HomeAI] starting voice server" + (" (" + reason + ")" if reason else ""), file=sys.stderr, flush=True)
    return True


def voice_boot():
    if CFG.get("voice_autostart") and voice_installed() and not voice_alive():
        voice_start("startup")


# ---------- private web search (SearXNG) ----------
# Searching only talks to SearXNG on loopback. Page fetches (optional) go straight to the result sites from this
# process: http(s) only, public addresses only (no LAN / loopback targets), 8 s timeout, at most 1 MB, text kept.
WEB_MAX_RESULTS = 8
WEB_FETCH_PAGES = 3
WEB_FETCH_TIMEOUT = 8
WEB_FETCH_MAX_BYTES = 1 << 20
WEB_PAGE_CHARS = 3000
WEB_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
_NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # never route through a system proxy


def searx_alive(timeout=2):
    try:
        with _NO_PROXY.open(CFG["searxng_url"] + "/healthz", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def searx_search(query, n=6, timeout=12):
    qs = urllib.parse.urlencode({"q": query, "format": "json", "safesearch": "0", "language": "en-GB", "pageno": "1"})
    req = urllib.request.Request(CFG["searxng_url"] + "/search?" + qs, headers={
        "Accept": "application/json", "Accept-Language": "en-GB,en;q=0.8", "User-Agent": "HomeAI/" + VERSION,
        "X-Forwarded-For": "127.0.0.1", "X-Real-IP": "127.0.0.1"})
    with _NO_PROXY.open(req, timeout=timeout) as r:
        data = json.loads(r.read(4 * WEB_FETCH_MAX_BYTES).decode("utf-8", "replace") or "{}")
    out, seen = [], set()
    for it in data.get("results") or []:
        url = str(it.get("url") or "").strip()
        if not url.startswith(("http://", "https://")) or url in seen:
            continue
        seen.add(url)
        out.append({"title": " ".join(str(it.get("title") or url).split())[:200], "url": url,
                    "content": " ".join(html.unescape(re.sub(r"<[^>]+>", "", str(it.get("content") or ""))).split())[:500]})
        if len(out) >= n:
            break
    return out


class _TextOnly(html.parser.HTMLParser):
    """Visible text of a page; the text inside <main>/<article> is also kept apart (preferred when there is enough)."""
    SKIP = {"script", "style", "noscript", "svg", "head", "template", "iframe", "nav", "footer", "form"}
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "pre", "blockquote"}
    MAIN = {"main", "article"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.main, self.skip, self.in_main = [], [], 0, 0

    def _add(self, t):
        self.parts.append(t)
        if self.in_main:
            self.main.append(t)

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.MAIN:
            self.in_main += 1
        if tag in self.BLOCK:
            self._add("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag in self.MAIN and self.in_main:
            self.in_main -= 1
        if tag in self.BLOCK:
            self._add("\n")

    def handle_data(self, data):
        if not self.skip:
            self._add(data)


def html_to_text(raw):
    p = _TextOnly()
    try:
        p.feed(raw)
        p.close()
    except Exception:
        pass
    tidy = lambda parts: "\n".join(x for x in (" ".join(ln.split()) for ln in "".join(parts).splitlines()) if x)
    main = tidy(p.main)
    return main if len(main) >= 400 else tidy(p.parts)


def _public_host(host):
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    return bool(infos) and all(ipaddress.ip_address(i[4][0].split("%")[0]).is_global for i in infos)


class _PublicOnlyRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        u = urllib.parse.urlsplit(newurl)
        if u.scheme not in ("http", "https") or not _public_host(u.hostname or ""):
            raise urllib.error.URLError("redirect to a non-public address blocked")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_PAGE_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _PublicOnlyRedirects())


def fetch_page_text(url):
    u = urllib.parse.urlsplit(url)
    if u.scheme not in ("http", "https") or not _public_host(u.hostname or ""):
        raise ValueError("not a public http(s) address")
    req = urllib.request.Request(url, headers={"User-Agent": WEB_UA, "Accept": "text/html,text/plain;q=0.9,*/*;q=0.1",
                                               "Accept-Language": "en-GB,en;q=0.8", "Accept-Encoding": "identity"})
    with _PAGE_OPENER.open(req, timeout=WEB_FETCH_TIMEOUT) as r:
        ctype = (r.headers.get("Content-Type") or "").lower()
        if ctype and not ctype.startswith(("text/html", "text/plain", "application/xhtml")):
            raise ValueError("not a text page (%s)" % ctype.split(";")[0])
        raw = r.read(WEB_FETCH_MAX_BYTES)
        charset = r.headers.get_content_charset() or "utf-8"
    try:
        txt = raw.decode(charset, "replace")
    except LookupError:
        txt = raw.decode("utf-8", "replace")
    txt = txt if ctype.startswith("text/plain") else html_to_text(txt)
    return txt[:WEB_PAGE_CHARS].rstrip() + (" …" if len(txt) > WEB_PAGE_CHARS else "")


def web_context(results):
    """The block the UI puts in front of the user's message (numbers match the Sources list)."""
    lines = ["Web results (cite as [1], [2]...). Current date: %s. Use them when relevant, cite the numbers inline, "
             "and say so if they do not answer the question." % time.strftime("%Y-%m-%d")]
    for i, r in enumerate(results, 1):
        lines.append("")
        lines.append("[%d] %s\nURL: %s" % (i, r["title"], r["url"]))
        if r.get("content"):
            lines.append(r["content"])
        if r.get("text"):
            lines.append("Page text:\n" + r["text"])
    return "\n".join(lines)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "HomeAI/" + VERSION

    def log_message(self, fmt, *args):
        if os.environ.get("HOMEAI_VERBOSE"):
            sys.stderr.write("[HomeAI] %s - %s\n" % (self.address_string(), fmt % args))

    # ---------- helpers ----------
    def send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status, msg):
        self.send_json({"error": {"code": status, "message": msg}}, status)

    def read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n > 0 else b""

    def read_json_body(self):
        raw = self.read_body()
        return json.loads(raw.decode("utf-8")) if raw else {}

    def same_origin_ok(self):
        # Basic CSRF / DNS-rebinding guard: only accept our own Host.
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        allowed = {"127.0.0.1", "localhost", "[::1]", str(CFG["host"]).lower()}
        if CFG["host"] in ("0.0.0.0", "::"):
            return True
        return host in allowed

    # ---------- routing ----------
    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def do_PUT(self):
        self.route("PUT")

    def do_DELETE(self):
        self.route("DELETE")

    def do_PATCH(self):
        self.route("PATCH")

    def route(self, method):
        try:
            if not self.same_origin_ok():
                return self.send_error_json(403, "forbidden host")
            path = urllib.parse.urlsplit(self.path).path
            if path == "/installed.js" or path.startswith("/api/modes"):
                import modes_api
                if modes_api.handle(self, method, path, CFG):
                    return
            if path.startswith("/api/llama/") or path == "/api/llama":
                return self.proxy(method)
            m = re.match(r"^/api/voice/(health|voices|stt|tts)$", path)
            if m:
                return self.voice_proxy(method, m.group(1))
            if path == "/api/info" and method == "GET":
                return self.send_json({"app": "HomeAI", "version": VERSION, "llama_url": CFG["llama_url"],
                                       "data_dir": CFG["data_dir"], "searxng_url": CFG["searxng_url"]})
            if path == "/api/websearch":
                return self.websearch(method)
            if path == "/api/chats" and method == "GET":
                return self.list_chats()
            m = re.match(r"^/api/chats/([^/]+)$", path)
            if m:
                return self.chat_item(method, m.group(1))
            if path == "/api/openhands/status" and method == "GET":
                return self.oh_status()
            if path == "/api/openhands/start" and method == "POST":
                return self.oh_start()
            if path == "/api/openhands/send" and method == "POST":
                return self.oh_send()
            if path == "/api/secure-delete/status" and method == "GET":
                with _RETRIM["lock"]:
                    st = {"retrim_running": _RETRIM["running"], "retrim_last": _RETRIM["last"],
                          "retrim_result": _RETRIM["result"]}
                st["log"] = SECURE_LOG[-20:]
                return self.send_json(st)
            m = re.match(r"^/api/store/(presets|settings)$", path)
            if m:
                return self.store_item(method, m.group(1))
            if method in ("GET", "HEAD"):
                return self.static(path)
            self.send_error_json(404, "not found")
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as e:  # noqa
            try:
                self.send_error_json(500, f"{type(e).__name__}: {e}")
            except Exception:
                pass

    # ---------- static ----------
    def static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        rel = urllib.parse.unquote(path).lstrip("/").replace("\\", "/")
        full = os.path.normpath(os.path.join(STATIC_DIR, rel))
        if not full.startswith(os.path.normpath(STATIC_DIR) + os.sep) or not os.path.isfile(full):
            if "." not in os.path.basename(rel):  # SPA fallback
                full = os.path.join(STATIC_DIR, "index.html")
            else:
                return self.send_error_json(404, "not found")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache" if full.endswith((".html", ".js", ".css")) else "max-age=86400")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    # ---------- chats ----------
    def list_chats(self):
        out = []
        for name in os.listdir(CHATS_DIR):
            if name.endswith(".json"):
                meta = chat_meta(name[:-5])
                if meta:
                    out.append(meta)
        out.sort(key=lambda c: (not c["pinned"], -float(c["updated"] or 0)))
        self.send_json({"chats": out})

    def chat_item(self, method, chat_id):
        if not ID_RE.match(chat_id):
            return self.send_error_json(400, "bad id")
        path = os.path.join(CHATS_DIR, chat_id + ".json")
        if method == "GET":
            c = read_json(path)
            return self.send_json(c) if c is not None else self.send_error_json(404, "chat not found")
        if method in ("PUT", "PATCH") and chat_id in DELETED_IDS:
            self.read_body()
            return self.send_error_json(410, "chat was deleted")
        if method == "PUT":
            c = self.read_json_body()
            c["id"] = chat_id
            c.setdefault("created", time.time())
            with WRITE_LOCK:
                if chat_id in DELETED_IDS:
                    return self.send_error_json(410, "chat was deleted")
                atomic_write_json(path, c)
                _meta_cache.pop(chat_id, None)
            return self.send_json({"ok": True, "meta": chat_meta(chat_id)})
        if method == "PATCH":  # partial update: title / pinned
            patch = self.read_json_body()
            with WRITE_LOCK:
                c = read_json(path)
                if c is None:
                    return self.send_error_json(404, "chat not found")
                for k in ("title", "pinned"):
                    if k in patch:
                        c[k] = patch[k]
                atomic_write_json(path, c)
                _meta_cache.pop(chat_id, None)
            return self.send_json({"ok": True, "meta": chat_meta(chat_id)})
        if method == "DELETE":
            # secure delete: the chat file plus any leftover temp file from an interrupted save
            wiped, errors = [], []
            with WRITE_LOCK:
                DELETED_IDS.add(chat_id)
                for p in (path, path + ".tmp"):
                    try:
                        if secure_wipe_file(p):
                            wiped.append(os.path.basename(p))
                    except Exception as e:  # noqa - never leave the chat behind
                        errors.append(f"{os.path.basename(p)}: {type(e).__name__}: {e}")
                        try:
                            os.remove(p)
                        except FileNotFoundError:
                            pass
                _meta_cache.pop(chat_id, None)
            retrim = request_retrim() if wiped or errors else "skipped (nothing deleted)"
            _slog(f"secure delete {len(wiped)} file(s), {len(errors)} error(s); retrim {retrim}")
            resp = {"ok": True, "secure": not errors, "wiped": len(wiped), "retrim": retrim}
            if errors:
                resp["warnings"] = errors
            return self.send_json(resp)
        self.send_error_json(405, "method not allowed")

    def store_item(self, method, name):
        path = os.path.join(CFG["data_dir"], name + ".json")
        if method == "GET":
            return self.send_json({"value": read_json(path)})
        if method == "PUT":
            body = self.read_json_body()
            with WRITE_LOCK:
                atomic_write_json(path, body.get("value"))
            return self.send_json({"ok": True})
        self.send_error_json(405, "method not allowed")

    # ---------- OpenHands bridge ----------
    def oh_status(self):
        alive = oh_alive()
        self.send_json({"running": alive, "starting": (not alive) and oh_starting(), "ui_url": oh_ui_url(),
                        "workspace": CFG["openhands_workspace_host"],
                        "can_start": os.path.isfile(CFG["openhands_launcher"])})

    def oh_start(self):
        if oh_alive():
            return self.send_json({"ok": True, "running": True})
        launcher = CFG["openhands_launcher"]
        if not os.path.isfile(launcher):
            return self.send_error_json(404, f"launcher not found: {launcher}")
        with _OH_LOCK:
            if not oh_starting():
                flags = 0
                if os.name == "nt":
                    flags = subprocess.CREATE_NEW_CONSOLE | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                cmd = (["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Minimized",
                        "-File", launcher] if launcher.lower().endswith(".ps1") else ["bash", launcher])
                subprocess.Popen(cmd,
                                 cwd=os.path.dirname(launcher) or None, creationflags=flags,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 close_fds=True)
                _OH_START["t"] = time.time()
        self.send_json({"ok": True, "running": False, "starting": True})

    def oh_send(self):
        req = self.read_json_body()
        task = str(req.get("task") or "").strip()
        if not task:
            return self.send_error_json(400, "empty task")
        if not oh_alive():
            return self.send_json({"error": {"code": 503, "message": "OpenHands is not running"},
                                   "not_running": True, "starting": oh_starting(),
                                   "can_start": os.path.isfile(CFG["openhands_launcher"])}, 503)
        try:
            key = oh_session_key()
            settings = oh_http("GET", "/api/settings", key=key) or {}
            hexid = uuid.uuid4().hex
            body = {
                "conversation_id": str(uuid.UUID(hexid)),
                "workspace": {"kind": "LocalWorkspace",
                              "working_dir": CFG["openhands_workspace_container"].rstrip("/") + "/project/" + hexid},
                "initial_message": {"role": "user", "content": [{"type": "text", "text": task}], "run": True},
                "tags": {"clientsource": "agentcanvas", "source": "homeai"},
            }
            if settings.get("active_agent_profile_id"):
                body["agent_profile_id"] = settings["active_agent_profile_id"]
            info = oh_http("POST", "/api/conversations", body=body, key=key, timeout=120) or {}
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:600]
            return self.send_error_json(502, f"OpenHands rejected the request (HTTP {e.code}): {detail}")
        except Exception as e:  # noqa
            return self.send_error_json(502, f"OpenHands request failed: {type(e).__name__}: {e}")
        cid = str(info.get("id") or body["conversation_id"])
        folder = os.path.join(CFG["openhands_workspace_host"], "project", cid.replace("-", ""))
        self.send_json({"ok": True, "conversation_id": cid, "url": oh_ui_url(cid), "files_dir": folder,
                        "status": info.get("execution_status"),
                        "model": ((info.get("agent") or {}).get("llm") or {}).get("model")})

    # ---------- web search (SearXNG + optional page text) ----------
    def websearch(self, method):
        if method == "GET":
            return self.send_json({"searxng_url": CFG["searxng_url"], "alive": searx_alive()})
        if method != "POST":
            self.read_body()
            return self.send_error_json(405, "method not allowed")
        req = self.read_json_body()
        q = " ".join(str(req.get("q") or "").split())[:200]
        if not q:
            return self.send_error_json(400, "empty query")
        n = max(1, min(WEB_MAX_RESULTS, int(req.get("n") or 6)))
        t0 = time.time()
        try:
            results = searx_search(q, n)
        except Exception as e:  # noqa
            why = getattr(e, "reason", None) or e
            return self.send_json({"error": {"code": 502, "message": f"SearXNG is not reachable at {CFG['searxng_url']} ({why})"},
                                   "query": q, "results": []}, 502)
        fetched = 0
        if req.get("fetch") and results:
            def grab(r):
                try:
                    r["text"] = fetch_page_text(r["url"])
                except Exception as e:  # noqa - a page that fails just keeps its snippet
                    r["fetch_error"] = f"{type(e).__name__}: {e}"[:160]
            ts = [threading.Thread(target=grab, args=(r,), daemon=True) for r in results[:WEB_FETCH_PAGES]]
            for t in ts:
                t.start()
            for t in ts:
                t.join(WEB_FETCH_TIMEOUT + 4)
            fetched = sum(1 for r in results if r.get("text"))
        self.send_json({"ok": True, "query": q, "results": results, "fetched": fetched,
                        "context": web_context(results) if results else "", "ms": int((time.time() - t0) * 1000)})

    # ---------- voice sidecar proxy (buffered; requests and replies are small) ----------
    def voice_proxy(self, method, what):
        want = "GET" if what in ("health", "voices") else "POST"
        if method != want:
            self.read_body()
            return self.send_error_json(405, "method not allowed")
        n = int(self.headers.get("Content-Length") or 0)
        if n > VOICE_MAX_UPLOAD:
            self.close_connection = True
            return self.send_error_json(413, "recording too long")
        body = self.read_body() if want == "POST" else None
        query = urllib.parse.urlsplit(self.path).query
        headers = {"Content-Type": self.headers.get("Content-Type") or "application/octet-stream"}
        if body is not None:
            headers["Content-Length"] = str(len(body))
        conn = http.client.HTTPConnection(VOICE.hostname, VOICE.port or 80, timeout=300)
        try:
            try:
                conn.request(want, "/" + what + ("?" + query if query else ""), body=body, headers=headers)
                up = conn.getresponse()
                data = up.read()
            except (ConnectionRefusedError, OSError):
                started = voice_start("on demand")
                return self.send_json({"error": {"code": 503, "message": "Voice engine is starting, try again in a few seconds" if started
                                                 else "Voice engine is not installed (voice-venv / voice\\voice_server.py missing)"},
                                       "starting": started, "installed": voice_installed()}, 503)
            self.send_response(up.status)
            for k in ("Content-Type", "X-Synth-Ms", "X-Audio-Seconds"):
                if up.getheader(k):
                    self.send_header(k, up.getheader(k))
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        finally:
            conn.close()

    # ---------- reverse proxy (streaming) ----------
    def proxy(self, method):
        parts = urllib.parse.urlsplit(self.path)
        sub = parts.path[len("/api/llama"):] or "/"
        target = (LLAMA.path.rstrip("/") + sub) + (("?" + parts.query) if parts.query else "")
        body = self.read_body() if method in ("POST", "PUT", "PATCH", "DELETE") else None
        if method not in ("GET", "HEAD"):
            ep = sub.rstrip("/").lower() or "/"
            if method != "POST" or ep not in ALLOWED_POST:
                return self.send_error_json(403, "this llama-server endpoint is not available through HomeAI")
            if ep in ("/v1/chat/completions", "/chat/completions"):
                try:
                    body = apply_safety(body or b"")
                except ValueError as e:
                    return self.send_error_json(400, str(e))
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_HEADERS
                   and k.lower() not in ("origin", "referer", "cookie", "accept-encoding")}
        headers["Accept-Encoding"] = "identity"
        if CFG.get("api_key"):
            headers["Authorization"] = "Bearer " + CFG["api_key"]
        if body is not None:
            headers["Content-Length"] = str(len(body))
        conn_cls = http.client.HTTPSConnection if LLAMA.scheme == "https" else http.client.HTTPConnection
        port = LLAMA.port or (443 if LLAMA.scheme == "https" else 80)
        # long timeout: in router mode a request may block while a model is being swapped in
        conn = conn_cls(LLAMA.hostname, port, timeout=1800)
        try:
            try:
                conn.request(method, target, body=body, headers=headers)
                up = conn.getresponse()
            except (ConnectionRefusedError, OSError) as e:
                return self.send_error_json(502, f"llama-server unreachable at {CFG['llama_url']} ({e})")
            self.send_response(up.status, up.reason)
            for k, v in up.getheaders():
                if k.lower() not in HOP_HEADERS:
                    self.send_header(k, v)
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("X-Accel-Buffering", "no")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            while True:
                chunk = up.read1(65536) if hasattr(up, "read1") else up.read(4096)
                if not chunk:
                    break
                # pass through immediately (no buffering); a write error means the browser
                # went away (Stop button) -> closing upstream makes llama-server cancel the task
                self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        finally:
            try:
                conn.close()
            except Exception:
                pass


def main():
    url = f"http://{'127.0.0.1' if CFG['host'] in ('0.0.0.0', '::') else CFG['host']}:{CFG['port']}/"
    want_open = "--open" in sys.argv or CFG.get("open_browser")
    try:
        httpd = ThreadingHTTPServer((CFG["host"], CFG["port"]), Handler)
    except OSError as e:
        print(f"[HomeAI] Could not listen on {CFG['host']}:{CFG['port']} ({e}).", flush=True)
        print("[HomeAI] Is HomeAI already running? Otherwise change \"port\" in config.json.", flush=True)
        if want_open:
            import webbrowser
            webbrowser.open(url)
        sys.exit(2)
    httpd.daemon_threads = True
    print(f"[HomeAI] v{VERSION} serving {url}", flush=True)
    print(f"[HomeAI] llama-server: {CFG['llama_url']}", flush=True)
    print(f"[HomeAI] data folder : {CFG['data_dir']}", flush=True)
    print(f"[HomeAI] web search  : {CFG['searxng_url']} (SearXNG)", flush=True)
    if voice_installed():
        print(f"[HomeAI] voice (local STT/TTS): {CFG['voice_url']}", flush=True)
        threading.Thread(target=voice_boot, daemon=True).start()
    if want_open:
        import webbrowser
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[HomeAI] bye")


if __name__ == "__main__":
    main()
