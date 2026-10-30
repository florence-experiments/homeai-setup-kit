"""Install HomeAI itself and the optional extras into the HomeAI folder.

Every function is safe to run again (setup can be re-run to add or repair extras). Downloads are verified: SHA-256
for large files, Hugging Face's git hash for small ones. Nothing here sends anything anywhere."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys

from . import hfcore as H
from . import hfsearch as S
from .llamacpp import download as gh_download
from .util import IS_WIN, PAYLOAD_DIR, run, say

VOICE_PIP = ["faster-whisper>=1.1,<2", "kokoro-onnx>=0.4,<1", "av<16"]  # faster-whisper 1.2 still passes an argument PyAV 16+ removed
KOKORO = [  # GitHub release thewh1teagle/kokoro-onnx model-files-v1.0 (hashes pinned by the kit)
    ("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx", "kokoro-v1.0.onnx",
     325532387, "7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5"),
    ("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin", "voices-v1.0.bin",
     28214398, "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d"),
]
WHISPER_REPO = "Systran/faster-whisper-small.en"
WHISPER = [  # (file, size, sha256 or None, git blob sha1)
    ("model.bin", 483545366, "62b2a45b05ee59acb4a5341b33ee35e041395d378d418a18acfe4c9e768ee37a", None),
    ("config.json", 2657, None, "ced3fd5bbb3e9f7664658065d2d36164712cf1d5"),
    ("tokenizer.json", 2128466, None, "15d7bdf9ba25718ca2504eec6a8f02bc55af0a6a"),
    ("vocabulary.txt", 422309, None, "ee695b8d3e3c10d488304e04468efec4ca27554a"),
]
OPENHANDS_IMAGE = "ghcr.io/openhands/agent-canvas:1.33.0"
SEARXNG_IMAGE = "docker.io/searxng/searxng:latest"

# rough download sizes for the summary shown before the user types yes
SIZES_GB = {"voice": 1.2, "searxng": 0.3, "openhands": 3.5, "updater": 0.0, "security": 0.1}
DESCR = {"voice": "Voice: speech-to-text (Whisper small.en) + text-to-speech (Kokoro) + Python packages",
         "searxng": "Web search: SearXNG Docker image", "openhands": "OpenHands: Docker image " + OPENHANDS_IMAGE,
         "updater": "Model Updater (no download)", "security": "Security Monitor (Sysmon + offline geo files are downloaded "
                                                               "later, when you run its Install-All.cmd)"}


def copytree(src, dst, keep=()):
    """Copy src over dst; names in keep (e.g. 'data') are never overwritten if they already exist in dst."""
    os.makedirs(dst, exist_ok=True)
    for name in os.listdir(src):
        s, d = os.path.join(src, name), os.path.join(dst, name)
        if name in keep and os.path.exists(d):
            continue
        if name == "__pycache__":
            continue
        if os.path.isdir(s):
            copytree(s, d)
        else:
            shutil.copy2(s, d)


def write(path, text, crlf=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\r\n" if crlf else "\n") as f:
        f.write(text)


def python_exe(root):
    p = os.path.join(root, "python", "python.exe")
    return p if IS_WIN and os.path.isfile(p) else sys.executable


# ------------------------------------------------------------------------------------------------ HomeAI app
def install_homeai(root, log=say):
    dst = os.path.join(root, "homeai")
    copytree(os.path.join(PAYLOAD_DIR, "homeai"), dst, keep=("data", "config.json"))
    cfg = os.path.join(dst, "config.json")
    if not os.path.exists(cfg):
        write(cfg, json.dumps({"host": "127.0.0.1", "port": 8090, "llama_url": "http://127.0.0.1:8081", "data_dir": "data",
                               "searxng_url": "http://127.0.0.1:8888", "voice_autostart": True}, indent=2) + "\n")
    os.makedirs(os.path.join(dst, "data"), exist_ok=True)
    log("   HomeAI app installed")


def install_kit(root):
    """A copy of the setup code lives in <root>/kit so '+ Add mode', the updater and the launchers work later."""
    src = os.path.dirname(os.path.abspath(__file__))
    dst = os.path.join(root, "kit", "homeai_setup")
    if os.path.abspath(src) != os.path.abspath(dst):
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        copytree(src, dst)
    icons = os.path.join(os.path.dirname(os.path.dirname(src)), "icons")
    if os.path.isdir(icons):
        copytree(icons, os.path.join(root, "kit", "icons"))


# ------------------------------------------------------------------------------------------------ voice
def _git_blob_sha1(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def install_voice(root, log=say):
    app = os.path.join(root, "homeai")
    venv = os.path.join(app, "voice-venv")
    vpy = os.path.join(venv, "Scripts", "python.exe") if IS_WIN else os.path.join(venv, "bin", "python")
    if not os.path.isfile(vpy):
        log("   creating the voice Python environment...")
        rc, out = run([python_exe(root), "-m", "venv", venv], timeout=600)
        if rc:
            raise RuntimeError("could not create a Python venv (%s)%s" % (out.strip()[-200:],
                               "" if IS_WIN else " - on Debian/Ubuntu run: sudo apt install python3-venv"))
    log("   installing voice packages (pip)...")
    rc, out = run([vpy, "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "-q"] + VOICE_PIP, timeout=3600)
    if rc:
        raise RuntimeError("pip install failed: " + out.strip()[-400:])
    kdir = os.path.join(app, "voice-models", "kokoro")
    os.makedirs(kdir, exist_ok=True)
    for url, name, size, sha in KOKORO:
        dest = os.path.join(kdir, name)
        if os.path.isfile(dest) and os.path.getsize(dest) == size:
            continue
        log("   downloading %s (%.0f MB)..." % (name, size / 1e6))
        gh_download(url, dest, size, sha)
    wdir = os.path.join(app, "voice-models", "whisper-small.en")
    os.makedirs(wdir, exist_ok=True)
    hf = S.hf_client(None)
    for name, size, sha, blob in WHISPER:
        dest = os.path.join(wdir, name)
        if os.path.isfile(dest) and os.path.getsize(dest) == size:
            continue
        log("   downloading whisper %s..." % name)
        if sha:
            ok, _ = H.download_file(hf, WHISPER_REPO, name, wdir, size, sha)
            if not ok:
                raise RuntimeError("whisper download failed - run setup again to resume")
        else:
            with hf.open(hf.file_url(WHISPER_REPO, name), timeout=60) as r:
                data = r.read()
            if _git_blob_sha1(data) != blob:
                raise RuntimeError("hash mismatch for whisper %s - not used" % name)
            with open(dest, "wb") as f:
                f.write(data)
    log("   voice installed (all files verified)")


# ------------------------------------------------------------------------------------------------ Docker extras
def docker_ok():
    rc, _ = run(["docker", "info"], timeout=30)
    return rc == 0


def install_searxng(root, log=say):
    d = os.path.join(root, "extras", "searxng")
    copytree(os.path.join(PAYLOAD_DIR, "searxng"), d)
    st = os.path.join(d, "config", "settings.yml")
    if not os.path.exists(st):
        with open(os.path.join(d, "settings.template.yml"), encoding="utf-8") as f:
            write(st, f.read().replace("{{SECRET}}", secrets.token_hex(32)))
    if docker_ok():
        log("   downloading the SearXNG image...")
        rc, out = run(["docker", "compose", "-f", os.path.join(d, "compose.yaml"), "pull"], timeout=1800)
        if rc:
            log("   could not pull SearXNG now (%s); it will be pulled at first start" % out.strip()[-160:])
    else:
        log("   Docker is not running - SearXNG will be downloaded the first time HomeAI starts with Docker running")
    log("   web search (SearXNG) installed: http://127.0.0.1:8888 (local only)")


def install_openhands(root, log=say):
    d = os.path.join(root, "extras", "openhands")
    copytree(os.path.join(PAYLOAD_DIR, "openhands"), d, keep=("state", "workspace"))
    os.makedirs(os.path.join(d, "workspace"), exist_ok=True)
    if IS_WIN:
        write(os.path.join(d, "Start-OpenHands.ps1"),
              "# Starts OpenHands (Docker) wired to HomeAI's local AI engine.\n"
              "& \"$PSScriptRoot\\..\\..\\python\\python.exe\" \"$PSScriptRoot\\openhands_ctl.py\" start\n", crlf=True)
        write(os.path.join(d, "Stop-OpenHands.ps1"),
              "& \"$PSScriptRoot\\..\\..\\python\\python.exe\" \"$PSScriptRoot\\openhands_ctl.py\" stop\n", crlf=True)
    else:
        for name, cmd in (("start-openhands.sh", "start"), ("stop-openhands.sh", "stop")):
            p = os.path.join(d, name)
            write(p, "#!/usr/bin/env bash\n# OpenHands (Docker) wired to HomeAI's local AI engine.\n"
                     "cd \"$(dirname \"$0\")\" && exec \"%s\" openhands_ctl.py %s \"$@\"\n" % (sys.executable, cmd))
            os.chmod(p, 0o755)
    if docker_ok():
        log("   downloading the OpenHands image (a few GB)...")
        rc, out = run(["docker", "pull", OPENHANDS_IMAGE], timeout=7200)
        if rc:
            log("   could not pull OpenHands now (%s); it will be pulled at first start" % out.strip()[-160:])
    else:
        log("   Docker is not running - the OpenHands image will be downloaded at its first start")
    log("   OpenHands installed (button in HomeAI, UI at http://127.0.0.1:3000/canvas)")


def install_updater(root, log=say):
    d = os.path.join(root, "extras", "model-updater")
    copytree(os.path.join(PAYLOAD_DIR, "model-updater"), d)
    if IS_WIN:
        write(os.path.join(d, "Run-Model-Updater.cmd"), "@echo off\r\nrem HomeAI Model Updater - nothing changes unless you type yes.\r\n"
              "\"%~dp0..\\..\\python\\python.exe\" \"%~dp0model_updater.py\" %*\r\n", crlf=False)
    else:
        p = os.path.join(d, "run-model-updater.sh")
        write(p, "#!/usr/bin/env bash\n# HomeAI Model Updater - nothing changes unless you type yes.\n"
                 "exec \"%s\" \"$(dirname \"$0\")/model_updater.py\" \"$@\"\n" % sys.executable)
        os.chmod(p, 0o755)
    log("   Model Updater installed")


def install_security(root, log=say):
    if not IS_WIN:
        log("   Security Monitor is Windows-only - skipped")
        return
    d = os.path.join(root, "extras", "security")
    copytree(os.path.join(PAYLOAD_DIR, "security"), d, keep=("config.json", "state", "logs", "geo"))
    for sub in ("state", "logs", "geo"):
        os.makedirs(os.path.join(d, sub), exist_ok=True)
    tokens = {"{{SEC}}": d, "{{HOMEAI_ROOT}}": root, "{{PYTHON}}": python_exe(root),
              "{{DRIVE}}": (os.path.splitdrive(root)[0] or "C:").rstrip(":")}

    def fill(v):
        if isinstance(v, str):
            for k, r in tokens.items():
                v = v.replace(k, r)
            return v
        if isinstance(v, list):
            return [fill(x) for x in v]
        if isinstance(v, dict):
            return {k: fill(x) for k, x in v.items()}
        return v
    cfg = os.path.join(d, "config.json")
    if not os.path.exists(cfg):
        with open(os.path.join(d, "config.template.json"), encoding="utf-8") as f:
            write(cfg, json.dumps(fill(json.load(f)), indent=2) + "\n")
    with open(os.path.join(d, "sysmon-override.template.xml"), encoding="utf-8") as f:
        write(os.path.join(d, "sysmon-override.xml"), fill(f.read()))
    log("   Security Monitor copied. To switch it on: right-click extras\\security\\Install-All.cmd > Run as administrator")


INSTALLERS = {"voice": install_voice, "searxng": install_searxng, "openhands": install_openhands,
              "updater": install_updater, "security": install_security}
