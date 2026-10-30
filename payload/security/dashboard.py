"""Security Monitor web page on 127.0.0.1:8095 (stdlib http.server only).

Safety: binds to 127.0.0.1 only; checks the Host header (blocks DNS-rebinding tricks); every
API call needs the random X-Token that is baked into the page, so other web sites open in the
browser can't trigger actions (a custom header forces a CORS pre-flight we never approve)."""
import http.server
import json
import os
import socketserver
import threading

HERE = os.path.dirname(os.path.abspath(__file__))


class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = False


def make_handler(engine, token, port):
    page_path = os.path.join(HERE, "dashboard_page.html")
    allowed_hosts = {"127.0.0.1:%d" % port, "localhost:%d" % port}

    class H(http.server.BaseHTTPRequestHandler):
        server_version = "SecurityMonitor"

        def log_message(self, *a):   # keep quiet; the watcher has its own log
            pass

        def _host_ok(self):
            return (self.headers.get("Host") or "").lower() in allowed_hosts

        def _send(self, code, body, ctype="application/json"):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, default=str).encode()
            elif isinstance(body, str):
                body = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                             "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self._host_ok():
                return self._send(403, {"error": "bad host"})
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                with open(page_path, "r", encoding="utf-8") as f:
                    html = f.read().replace("__TOKEN__", token)
                return self._send(200, html, "text/html")
            if path == "/api/state":
                if self.headers.get("X-Token") != token:
                    return self._send(403, {"error": "token"})
                return self._send(200, engine.state())
            if path == "/health":
                return self._send(200, {"ok": True})
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._host_ok() or self.headers.get("X-Token") != token:
                return self._send(403, {"error": "forbidden"})
            try:
                n = min(int(self.headers.get("Content-Length") or 0), 65536)
                req = json.loads(self.rfile.read(n) or b"{}")
            except (ValueError, json.JSONDecodeError):
                return self._send(400, {"error": "bad json"})
            path = self.path.split("?", 1)[0]
            if path == "/api/action":
                ok, msg = engine.action(req.get("action", ""), req.get("id"), req)
                return self._send(200 if ok else 400, {"ok": ok, "message": msg})
            if path == "/api/test":
                ok, msg = engine.run_test(req.get("kind", ""), req)
                return self._send(200 if ok else 400, {"ok": ok, "message": msg})
            return self._send(404, {"error": "not found"})

        def do_OPTIONS(self):          # never approve cross-origin pre-flights
            self._send(403, {"error": "no cors"})

    return H


def start(engine, host, port, token):
    if host not in ("127.0.0.1", "::1", "localhost"):
        host = "127.0.0.1"           # refuse to expose the monitor to the network
    srv = _Server((host, port), make_handler(engine, token, port))
    th = threading.Thread(target=srv.serve_forever, name="dashboard", daemon=True)
    th.start()
    return srv
