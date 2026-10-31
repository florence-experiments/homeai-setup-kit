"""Focused tests for the resilience fixes: corrupt caches, stale / reused PIDs, malformed model choices,
candidates without fit data, and bad downloads (local HTTP server). Standard library only:

    python -m unittest discover -s tests -v
"""
import hashlib
import http.server
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kit"))

from homeai_setup import addmode, configgen as C, control, hfcore as H, hfsearch as S, llamacpp  # noqa: E402

H.RETRY_SLEEP = 0
quiet = lambda: redirect_stdout(io.StringIO())  # noqa: E731


class FakeResp(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


# ------------------------------------------------------------------------------------------------ 1. cache
class CacheTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.hf = S.hf_client(self.d)
        self.calls = 0

        def fake_open(url, headers=None, timeout=60):
            self.calls += 1
            return FakeResp(json.dumps([{"id": "a/b"}]).encode())
        self.hf.open = fake_open
        self.url = self.hf.API + "/api/models/x"

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_corrupt_cache_is_a_miss_and_is_replaced(self):
        for junk in (b'[{"id": "a/', b"\xff\xfe\x00garbage", b""):
            cp = self.hf._cache_path(self.url)
            with open(cp, "wb") as f:
                f.write(junk)
            self.assertEqual(self.hf.get_json("/api/models/x"), [{"id": "a/b"}])
            with open(cp, encoding="utf-8") as f:
                self.assertEqual(json.load(f), [{"id": "a/b"}])
        self.assertEqual(self.calls, 3)
        self.assertEqual(self.hf.get_json("/api/models/x"), [{"id": "a/b"}])   # now a good cache hit
        self.assertEqual(self.calls, 3)

    def test_store_is_atomic_and_leaves_no_temp_files(self):
        cp = self.hf._cache_path(self.url)
        H.HF._store(cp, {"ok": 1})
        H.HF._store(cp, {"bad": object()})          # cannot be serialised: old cache must survive intact
        with open(cp, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"ok": 1})
        self.assertEqual(os.listdir(self.d), [os.path.basename(cp)])

    def test_non_json_network_answer_is_an_error_not_a_crash(self):
        self.hf.open = lambda *a, **k: FakeResp(b"<html>proxy login</html>")
        with mock_sleep():
            self.assertIsNone(self.hf.get_json("/api/models/y"))
        self.assertTrue(any("not valid JSON" in e for e in self.hf.errors))
        self.assertEqual(self.hf.tree("a/b"), [])
        self.assertEqual(self.hf.search("x"), [])

    def test_wrong_shape_answers(self):
        self.hf.open = lambda *a, **k: FakeResp(b'{"error": "nope"}')
        self.assertEqual(self.hf.tree("a/b"), [])
        self.assertEqual(S._search(self.hf, "t", None, "downloads", 5), [])
        self.hf.open = lambda *a, **k: FakeResp(b'[1, "x", {"type": "file"}, {"type": "file", "path": "m-Q4_K_M.gguf", '
                                                b'"size": 10, "lfs": "weird"}]')
        quants, _ = H.pick_files(self.hf.tree("c/d"))
        self.assertEqual(list(quants), ["Q4_K_M"])
        c = H.Cand({"id": "a/b-8B", "cardData": ["not", "a", "dict"], "gguf": "x", "downloads": "many"})
        self.assertEqual((c.base_models, c.downloads, c.api_arch), ([], 0, None))


class mock_sleep:
    def __enter__(self):
        self.orig = time.sleep
        time.sleep = lambda s: None

    def __exit__(self, *a):
        time.sleep = self.orig


# ------------------------------------------------------------------------------------------------ 2. pid files
@unittest.skipIf(os.name == "nt" or not os.path.isdir("/proc"), "Linux /proc checks")
class PidTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.procs = []

    def tearDown(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
            p.wait()
        shutil.rmtree(self.root, ignore_errors=True)

    def dummy(self, tag, new_session=True):
        cmd = [sys.executable, "-c", "import time; time.sleep(120)", tag]
        p = subprocess.Popen(cmd, start_new_session=new_session)
        self.procs.append(p)
        time.sleep(0.2)
        return p, cmd

    def alive(self, p, wait=3.0):
        end = time.time() + wait
        while time.time() < end:
            if p.poll() is not None:
                return False
            time.sleep(0.05)
        return p.poll() is None

    def pf(self, name="engine"):
        return control._pidfile(self.root, name)

    def test_own_process_is_stopped(self):
        cmd = [sys.executable, "-c", "import time; time.sleep(120)", "homeai-own"]
        p = control._spawn(self.root, "engine", cmd, self.root)
        self.procs.append(p)
        time.sleep(0.2)
        rec = control.read_pidfile(self.pf())
        self.assertEqual((rec["pid"], rec["cmd"]), (p.pid, cmd))
        self.assertIsNotNone(rec["start"])
        with quiet():
            self.assertTrue(control._kill(self.root, "engine", cmd))
        p.wait(3)
        self.assertEqual(p.returncode, -signal.SIGTERM)
        self.assertFalse(os.path.exists(self.pf()))

    def test_stale_pid_pointing_at_unrelated_process_is_not_killed(self):
        other, _ = self.dummy("unrelated-app")
        with open(self.pf(), "w") as f:
            json.dump({"pid": other.pid, "start": control._proc_start(other.pid),
                       "cmd": ["/opt/homeai/engine/llama.cpp/llama-server", "--port", "8081"]}, f)
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertFalse(control._kill(self.root, "engine"))
        self.assertTrue(self.alive(other, 0.5))
        self.assertFalse(os.path.exists(self.pf()))           # stale pid file cleaned up
        self.assertIn("nothing stopped", out.getvalue())

    def test_reused_pid_with_same_command_but_other_start_time_is_not_killed(self):
        other, cmd = self.dummy("looks-like-ours")
        with open(self.pf(), "w") as f:
            json.dump({"pid": other.pid, "start": control._proc_start(other.pid) - 1, "cmd": cmd}, f)
        with quiet():
            self.assertFalse(control._kill(self.root, "engine", cmd))
        self.assertTrue(self.alive(other, 0.5))

    def test_old_style_bare_number_pid_file(self):
        other, _ = self.dummy("unrelated")
        with open(self.pf(), "w") as f:
            f.write(str(other.pid))
        with quiet():
            self.assertFalse(control._kill(self.root, "engine", ["/x/llama-server", "--port", "8081"]))
            self.assertFalse(control._kill(self.root, "engine"))     # (pid file already gone)
        self.assertTrue(self.alive(other, 0.5))
        ours, cmd = self.dummy("legacy-ours")
        with open(self.pf(), "w") as f:
            f.write(str(ours.pid))
        with quiet():
            self.assertTrue(control._kill(self.root, "engine", cmd))
        ours.wait(3)
        self.assertIsNotNone(ours.poll())

    def test_dead_pid_and_garbage_pid_files(self):
        p, cmd = self.dummy("short")
        p.kill(); p.wait()
        for content in (json.dumps({"pid": p.pid, "cmd": cmd}), "not a pid", "", "-5", '{"pid": "x"}', "[1,2]"):
            with open(self.pf(), "w") as f:
                f.write(content)
            with quiet():
                self.assertFalse(control._kill(self.root, "engine", cmd))
            self.assertFalse(os.path.exists(self.pf()))
        with quiet():
            self.assertFalse(control._kill(self.root, "engine", cmd))   # no pid file at all

    def test_killpg_only_for_our_own_group(self):
        # not a group leader (shares the test's group): must get a plain kill, never killpg on our own group
        p, cmd = self.dummy("no-session", new_session=False)
        with open(self.pf(), "w") as f:
            json.dump({"pid": p.pid, "start": control._proc_start(p.pid), "cmd": cmd}, f)
        with quiet():
            self.assertTrue(control._kill(self.root, "engine"))
        p.wait(3)
        self.assertEqual(p.returncode, -signal.SIGTERM)


# ------------------------------------------------------------------------------------------------ 3. choices
GOOD = {"repo": "someone/Model-8B-GGUF", "quant": "Q4_K_M", "ctx": 8192,
        "files": [{"path": "Model-8B-Q4_K_M.gguf", "sha256": None, "size": 5}]}


def state():
    return {"prefs": {"ctx": 8192}, "models": {}, "modes": {}, "hw": {"backend": "cpu"}}


class ChoiceTests(unittest.TestCase):
    BAD = [None, [], {}, {"repo": "noslash", "quant": "Q4", "files": GOOD["files"]},
           dict(GOOD, files=[]), dict(GOOD, files=None), dict(GOOD, files=[{}]), dict(GOOD, files=[{"path": None}]),
           dict(GOOD, files=["x.gguf"]), dict(GOOD, files=[{"path": "x.txt"}]), dict(GOOD, quant=None),
           dict(GOOD, ctx="lots")]

    def test_register_model_rejects_malformed_choices_clearly(self):
        for bad in self.BAD:
            with self.assertRaises(C.BadChoice, msg=repr(bad)) as cm:
                C.register_model(state(), "/tmp/r", bad, "general")
            self.assertIn("search again", str(cm.exception))

    def test_register_model_good_choice(self):
        st = state()
        sec = C.register_model(st, "/tmp/r", GOOD, "general")
        self.assertTrue(st["models"][sec]["model"].endswith("Model-8B-Q4_K_M.gguf"))

    def test_apply_rejects_before_any_download(self):
        root = tempfile.mkdtemp()
        try:
            C.save_state(root, state())
            orig = H.download_file
            H.download_file = lambda *a, **k: self.fail("must not download")
            try:
                with self.assertRaises(ValueError):
                    addmode.apply(root, "general", dict(GOOD, files=[]), log=lambda m: None)
            finally:
                H.download_file = orig
        finally:
            shutil.rmtree(root)


# ------------------------------------------------------------------------------------------------ 4. scoring
class ScoreTests(unittest.TestCase):
    def searcher(self):
        return S.Searcher(hf=type("X", (), {"errors": []})(), hw={"backend": "cpu", "ram_gib": 32},
                          prefs={"ctx": 8192}, log=lambda m: None)

    def cand(self):
        c = H.Cand({"id": "someone/Model-8B-abliterated-GGUF", "downloads": 10, "likes": 1})
        c.pre = 1.0
        return c

    def test_candidate_without_fit_is_skipped_not_crashing(self):
        s = self.searcher()
        for fit in (None, {}, {"fits": True}, {"fits": True, "tps": None}):
            c = self.cand()
            c.fit = fit
            c.files = {"files": ["a.gguf"], "sha": [None], "size": 1}
            self.assertFalse(s.score("general", c).ok)
        c = self.cand()
        c.fit = {"fits": True, "tps": 20, "where": "cpu", "n_cpu_moe": 0}
        c.files = None
        self.assertFalse(s.score("general", c).ok)

    def test_run_keeps_good_and_drops_incomplete(self):
        s = self.searcher()
        good, broken = self.cand(), self.cand()
        good.fit = {"fits": True, "tps": 20.0, "where": "cpu", "n_cpu_moe": 0}
        good.files = {"files": ["m-Q4_K_M.gguf"], "sha": [None], "size": 5}
        good.quant, good.bpw, good.ctx = "Q4_K_M", 4.89, 8192
        broken.id = "other/Broken-8B-GGUF"          # ok=True but detail never filled it in
        s.gather = lambda m: [good, broken]
        s.prefilter = lambda m, c: c
        s.detail = lambda m, c: c
        res, _ = s.run("general")
        self.assertEqual([r["repo"] for r in res], [good.id])


# ------------------------------------------------------------------------------------------------ 5. downloads
DATA = os.urandom(300_000)
SHA = hashlib.sha256(DATA).hexdigest()


class Handler(http.server.BaseHTTPRequestHandler):
    mode = "normal"
    hits = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        Handler.hits.append((self.path, self.headers.get("Range")))
        mode = Handler.mode
        if mode == "404":
            self.send_error(404); return
        body, start = DATA, 0
        if mode == "corrupt" or (mode == "corrupt-once" and len(Handler.hits) == 1):
            body = bytes([DATA[0] ^ 1]) + DATA[1:]
        if mode == "oversize":
            body = DATA + b"extra"
        rng = self.headers.get("Range")
        if rng and mode not in ("ignore-range",):
            start = int(rng.split("=")[1].split("-")[0])
            if start >= len(body):
                self.send_response(416); self.send_header("Content-Range", "bytes */%d" % len(body))
                self.end_headers(); return
            if mode == "bad-range":
                start2 = max(0, start - 10)
            else:
                start2 = start
            self.send_response(206)
            if mode == "cut-always":
                self.send_header("Content-Range", "bytes %d-%d/%d" % (start, len(body) - 1, len(body)))
                self.send_header("Content-Length", str(len(body) - start))
                self.end_headers()
                self.wfile.write(body[start:start + 1000]); return
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start2, len(body) - 1, len(body)))
            self.send_header("Content-Length", str(len(body) - start2))
            self.end_headers()
            self.wfile.write(body[start2:]); return
        self.send_response(200)
        if mode != "no-length":
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if mode in ("cut", "cut-always"):
            self.wfile.write(body[:1000]); return
        self.wfile.write(body)


class FakeHF:
    def __init__(self, port):
        self.port = port

    def file_url(self, repo, path):
        return "http://127.0.0.1:%d/%s" % (self.port, path)

    def open(self, url, headers=None, timeout=60):
        return urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=timeout)


class DownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.hf = FakeHF(cls.srv.server_address[1])

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        self.d = tempfile.mkdtemp()
        Handler.hits = []
        Handler.mode = "normal"
        self.final = os.path.join(self.d, "m.gguf")
        self.part = self.final + ".part"

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def dl(self, size=len(DATA), sha=SHA):
        out = io.StringIO()
        with redirect_stdout(out):
            ok, path = H.download_file(self.hf, "r/x", "m.gguf", self.d, size, sha)
        self.log = out.getvalue()
        return ok, path

    def assert_good(self, ok, path):
        self.assertTrue(ok, self.log)
        with open(path, "rb") as f:
            self.assertEqual(f.read(), DATA)
        self.assertFalse(os.path.exists(self.part))

    def assert_failed(self, ok, path):
        self.assertFalse(ok, self.log)
        self.assertIsNone(path)
        self.assertFalse(os.path.exists(self.final))

    def write_part(self, b):
        with open(self.part, "wb") as f:
            f.write(b)

    def test_normal(self):
        self.assert_good(*self.dl())

    def test_resume_from_good_partial(self):
        self.write_part(DATA[:1234])
        self.assert_good(*self.dl())
        self.assertEqual(Handler.hits[0][1], "bytes=1234-")

    def test_partial_larger_than_expected_is_deleted_and_refetched(self):
        self.write_part(DATA + b"junk")
        self.assert_good(*self.dl())
        self.assertIsNone(Handler.hits[0][1])
        self.assertFalse([f for f in os.listdir(self.d) if "oversize" in f])

    def test_server_ignoring_range_restarts_cleanly(self):
        Handler.mode = "ignore-range"
        self.write_part(DATA[:5000])
        self.assert_good(*self.dl())
        self.assertIn("ignored resume", self.log)

    def test_server_resuming_at_wrong_offset(self):
        Handler.mode = "bad-range"
        self.write_part(DATA[:5000])
        self.assert_good(*self.dl())

    def test_full_size_partial_with_bad_bytes_is_retried_once(self):
        self.write_part(b"\0" * len(DATA))            # right size, wrong content (bad resume state)
        self.assert_good(*self.dl())
        self.assertIn("trying once more", self.log)

    def test_sha_mismatch_once_then_good(self):
        Handler.mode = "corrupt-once"
        self.assert_good(*self.dl())
        self.assertEqual(len(Handler.hits), 2)

    def test_sha_mismatch_twice_fails_and_cleans_up(self):
        Handler.mode = "corrupt"
        self.assert_failed(*self.dl())
        self.assertFalse(os.listdir(self.d), "bad partial must be deleted")
        self.assertIn("FAILED again", self.log)

    def test_server_sends_too_much(self):
        Handler.mode = "oversize"
        self.assert_failed(*self.dl())
        self.assertIn("server says this file is", self.log)

    def test_listing_size_differs_from_file(self):
        self.assert_failed(*self.dl(size=len(DATA) - 1, sha=None))

    def test_missing_sha_verifies_size_and_warns(self):
        ok, path = self.dl(sha=None)
        self.assert_good(ok, path)
        self.assertIn("no SHA-256", self.log)
        self.assertIn("size verified", self.log)

    def test_unknown_size_learned_from_server(self):
        self.assert_good(*self.dl(size=None))

    def test_nothing_known_is_refused(self):
        Handler.mode = "no-length"
        self.assert_failed(*self.dl(size=None, sha=None))
        self.assertIn("cannot be verified", self.log)

    def test_invalid_sha_value_is_treated_as_missing(self):
        ok, _ = self.dl(sha="1234abcd")               # git sha1-ish / junk: not a SHA-256
        self.assertTrue(ok, self.log)
        self.assertIn("not a SHA-256", self.log)

    def test_connection_cut_is_resumed(self):
        Handler.mode = "cut"                          # first answer cut short, the resumed (Range) answer is fine
        self.assert_good(*self.dl())
        self.assertEqual(Handler.hits[1][1], "bytes=1000-")

    def test_connection_keeps_dropping_keeps_partial_for_later_resume(self):
        Handler.mode = "cut-always"
        self.assert_failed(*self.dl())
        self.assertIn("incomplete", self.log)
        self.assertEqual(os.path.getsize(self.part), 6000)
        Handler.mode = "normal"
        Handler.hits = []
        self.assert_good(*self.dl())
        self.assertEqual(Handler.hits[0][1], "bytes=6000-")

    def test_http_404_fails_fast(self):
        Handler.mode = "404"
        self.assert_failed(*self.dl())
        self.assertEqual(len(Handler.hits), 1)

    def test_existing_file_checks(self):
        with open(self.final, "wb") as f:
            f.write(DATA)
        self.assertTrue(self.dl()[0])
        self.assertFalse(self.dl(size=len(DATA) + 1)[0])
        self.assertFalse(self.dl(size=None, sha=None)[0])
        self.assertEqual(Handler.hits, [])

    def test_addmode_never_reports_success_on_bad_download(self):
        root = tempfile.mkdtemp()
        try:
            C.save_state(root, state())
            Handler.mode = "corrupt"
            orig = S.hf_client
            S.hf_client = lambda cache, token=None: self.hf
            try:
                pick = dict(GOOD, files=[{"path": "m.gguf", "sha256": SHA, "size": len(DATA)}])
                with quiet(), self.assertRaises(RuntimeError):
                    addmode.apply(root, "general", pick, log=lambda m: None)
                self.assertEqual(C.load_state(root)["modes"], {})
                Handler.mode = "normal"
                with quiet():
                    sec = addmode.apply(root, "general", pick, log=lambda m: None)
                self.assertEqual(C.load_state(root)["modes"]["general"]["section"], sec)
            finally:
                S.hf_client = orig
        finally:
            shutil.rmtree(root)

    def test_llamacpp_download_retries_bad_sha_and_rejects(self):
        orig = llamacpp._open
        llamacpp._open = lambda url, timeout=60, headers=None: self.hf.open(url, headers, timeout)
        try:
            dest = os.path.join(self.d, "llama.tgz")
            Handler.mode = "corrupt"
            with quiet(), self.assertRaises(RuntimeError):
                llamacpp.download(self.hf.file_url("", "llama.tgz"), dest, len(DATA), SHA)
            self.assertFalse(os.path.exists(dest))
            Handler.mode = "corrupt-once"
            Handler.hits = []
            with quiet():
                llamacpp.download(self.hf.file_url("", "llama.tgz"), dest, len(DATA), SHA)
            with open(dest, "rb") as f:
                self.assertEqual(f.read(), DATA)
        finally:
            llamacpp._open = orig


if __name__ == "__main__":
    unittest.main()
