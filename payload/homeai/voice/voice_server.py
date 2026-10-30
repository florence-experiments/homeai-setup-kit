#!/usr/bin/env python3
"""
HomeAI voice sidecar - 100% local speech-to-text and text-to-speech on the CPU.

  STT: faster-whisper (CTranslate2, int8) - models in ..\\voice-models\\whisper-<name>
  TTS: Kokoro-82M via kokoro-onnx (onnxruntime) - models in ..\\voice-models\\kokoro

Runs in its own venv (<HomeAI folder>/homeai/voice-venv) and listens on 127.0.0.1 only. server.py starts it and
proxies /api/voice/* to it, so the browser only ever talks to HomeAI itself. No network access is
needed or attempted at runtime: Hugging Face is forced offline and models load from local folders.
Audio and text are processed in memory and never written to disk or logged.

  GET  /health          -> status, loaded models, timings of the last calls
  GET  /voices          -> available female English voices
  POST /stt?model=small.en   body = audio file (webm/ogg/wav/...)  -> {"text": ..., "ms": ...}
  POST /tts             body = {"text", "voice", "speed"}          -> audio/wav (24 kHz mono 16-bit)
"""
import os
os.environ["HF_HUB_OFFLINE"] = "1"            # never reach out to the Hub
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
import io
import json
import re
import sys
import threading
import time
import wave
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

VERSION = "1.0.0"
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # <HomeAI folder>
MODELS = os.environ.get("HOMEAI_VOICE_MODELS") or os.path.join(APP_DIR, "voice-models")
HOST = "127.0.0.1"
PORT = int(os.environ.get("HOMEAI_VOICE_PORT") or 8092)
CPU_THREADS = max(2, min(8, (os.cpu_count() or 8) // 2))
STT_MODELS = {"small.en": "whisper-small.en", "large-v3-turbo": "whisper-large-v3-turbo", "distil-small.en": "whisper-distil-small.en"}
STT_DEFAULT = "small.en"
KOKORO_MODEL = "kokoro-v1.0.onnx"
MAX_AUDIO_BYTES = 40 * 1024 * 1024
MAX_TTS_CHARS = 3000

# female English Kokoro voices (British first); label shown in the UI
VOICES = [
    ("bf_emma", "Emma", "British"), ("bf_isabella", "Isabella", "British"), ("bf_alice", "Alice", "British"),
    ("bf_lily", "Lily", "British"), ("af_heart", "Heart", "American"), ("af_bella", "Bella", "American"),
    ("af_nicole", "Nicole", "American"), ("af_sarah", "Sarah", "American"), ("af_aoede", "Aoede", "American"),
    ("af_kore", "Kore", "American"), ("af_sky", "Sky", "American"), ("af_nova", "Nova", "American"),
    ("af_jessica", "Jessica", "American"), ("af_river", "River", "American"), ("af_alloy", "Alloy", "American"),
]
VOICE_IDS = {v[0] for v in VOICES}
DEFAULT_VOICE = "bf_emma"

_stt = {}                       # name -> WhisperModel
_stt_lock = threading.Lock()    # one transcription at a time (they use all CPU threads anyway)
_tts = {"k": None}
_tts_lock = threading.Lock()
_load_lock = threading.Lock()
STATS = {"started": time.time(), "last_stt": None, "last_tts": None, "errors": 0, "load_error": None}


def log(msg):
    # status only - never transcripts or spoken text
    print(time.strftime("%H:%M:%S") + " [voice] " + msg, flush=True)


def get_stt(name):
    name = name if name in STT_MODELS else STT_DEFAULT
    m = _stt.get(name)
    if m is None:
        with _load_lock:
            m = _stt.get(name)
            if m is None:
                from faster_whisper import WhisperModel
                path = os.path.join(MODELS, STT_MODELS[name])
                if not os.path.isfile(os.path.join(path, "model.bin")):
                    raise RuntimeError("speech model not found: " + path)
                t = time.time()
                m = WhisperModel(path, device="cpu", compute_type="int8", cpu_threads=CPU_THREADS, local_files_only=True)
                _stt[name] = m
                log("loaded whisper %s in %.1fs" % (name, time.time() - t))
    return name, m


def get_tts():
    k = _tts["k"]
    if k is None:
        with _load_lock:
            k = _tts["k"]
            if k is None:
                from kokoro_onnx import Kokoro
                t = time.time()
                k = Kokoro(os.path.join(MODELS, "kokoro", KOKORO_MODEL), os.path.join(MODELS, "kokoro", "voices-v1.0.bin"))
                _tts["k"] = k
                log("loaded kokoro in %.1fs" % (time.time() - t))
    return k


def preload():
    try:
        k = get_tts()
        with _tts_lock:
            k.create("Ready.", voice=DEFAULT_VOICE, speed=1.0, lang="en-gb")   # warm-up
        get_stt(STT_DEFAULT)
        log("ready")
    except Exception as e:  # noqa
        STATS["load_error"] = "%s: %s" % (type(e).__name__, e)
        log("preload failed: " + STATS["load_error"])


def transcribe(data, model_name):
    from faster_whisper import decode_audio
    audio = decode_audio(io.BytesIO(data), sampling_rate=16000)
    dur = len(audio) / 16000.0
    if dur < 0.2:
        return {"text": "", "duration": dur, "ms": 0, "model": model_name}
    name, m = get_stt(model_name)
    t = time.time()
    with _stt_lock:
        segs, info = m.transcribe(audio, language="en", beam_size=5, vad_filter=True,
                                  vad_parameters={"min_silence_duration_ms": 500},
                                  condition_on_previous_text=False, without_timestamps=True)
        text = " ".join(s.text.strip() for s in segs if s.no_speech_prob < 0.8).strip()
    ms = int((time.time() - t) * 1000)
    text = re.sub(r"\s+", " ", text)
    STATS["last_stt"] = {"ms": ms, "audio_s": round(dur, 2), "model": name, "at": time.time()}
    return {"text": text, "duration": round(dur, 2), "ms": ms, "model": name}


def synth(text, voice, speed):
    import numpy as np
    k = get_tts()
    voice = voice if voice in VOICE_IDS else DEFAULT_VOICE
    speed = min(2.0, max(0.5, float(speed or 1.0)))
    lang = "en-gb" if voice.startswith("b") else "en-us"
    t = time.time()
    with _tts_lock:
        samples, sr = k.create(text, voice=voice, speed=speed, lang=lang)
    ms = int((time.time() - t) * 1000)
    pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm)
    dur = len(samples) / float(sr)
    STATS["last_tts"] = {"ms": ms, "audio_s": round(dur, 2), "chars": len(text), "voice": voice, "at": time.time()}
    return buf.getvalue(), ms, dur


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "HomeAI-Voice/" + VERSION

    def log_message(self, fmt, *args):
        pass

    def send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def err(self, status, msg):
        self.send_json({"error": {"code": status, "message": msg}}, status)

    def body(self, limit):
        n = int(self.headers.get("Content-Length") or 0)
        if n > limit:
            raise ValueError("request too large")
        return self.rfile.read(n) if n > 0 else b""

    def host_ok(self):
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        return host in ("127.0.0.1", "localhost", "[::1]")

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def route(self, method):
        try:
            if not self.host_ok():
                return self.err(403, "forbidden host")
            path, _, query = self.path.partition("?")
            q = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
            if path == "/health" and method == "GET":
                return self.send_json({"ok": True, "version": VERSION, "engine": "local-cpu",
                                       "tts_loaded": _tts["k"] is not None, "stt_loaded": sorted(_stt),
                                       "stt_models": [n for n, d in STT_MODELS.items() if os.path.isfile(os.path.join(MODELS, d, "model.bin"))],
                                       "default_voice": DEFAULT_VOICE, "cpu_threads": CPU_THREADS, **STATS})
            if path == "/voices" and method == "GET":
                return self.send_json({"default": DEFAULT_VOICE, "voices": [{"id": i, "name": n, "accent": a} for i, n, a in VOICES]})
            if path == "/stt" and method == "POST":
                data = self.body(MAX_AUDIO_BYTES)
                if not data:
                    return self.err(400, "no audio")
                return self.send_json(transcribe(data, q.get("model", STT_DEFAULT)))
            if path == "/tts" and method == "POST":
                req = json.loads(self.body(1 << 20).decode("utf-8") or "{}")
                text = re.sub(r"\s+", " ", str(req.get("text") or "")).strip()[:MAX_TTS_CHARS]
                if not text:
                    return self.err(400, "empty text")
                wav, ms, dur = synth(text, req.get("voice"), req.get("speed"))
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(wav)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Synth-Ms", str(ms))
                self.send_header("X-Audio-Seconds", "%.2f" % dur)
                self.end_headers()
                return self.wfile.write(wav)
            self.err(404, "not found")
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as e:  # noqa
            STATS["errors"] += 1
            log("error: %s" % type(e).__name__)
            try:
                self.err(500, "%s: %s" % (type(e).__name__, e))
            except Exception:
                pass


def watch_parent(pid):
    """Exit when the HomeAI server that started us goes away (Windows: wait on its process handle)."""
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x00100000, False, pid)   # SYNCHRONIZE
        if not h:
            return
        k32.WaitForSingleObject(h, 0xFFFFFFFF)
        log("HomeAI (pid %d) exited - stopping voice server" % pid)
        os._exit(0)
    except Exception:
        pass


def main():
    if "--parent-pid" in sys.argv and os.name == "nt":
        pid = int(sys.argv[sys.argv.index("--parent-pid") + 1])
        threading.Thread(target=watch_parent, args=(pid,), daemon=True).start()
    try:
        httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as e:
        log("could not listen on %s:%d (%s) - already running?" % (HOST, PORT, e))
        sys.exit(2)
    httpd.daemon_threads = True
    log("v%s listening on http://%s:%d (models: %s, %d CPU threads)" % (VERSION, HOST, PORT, MODELS, CPU_THREADS))
    if "--no-preload" not in sys.argv:
        threading.Thread(target=preload, daemon=True).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
