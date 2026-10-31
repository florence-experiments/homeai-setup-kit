"""install.json (what was installed), models.ini (llama.cpp router presets), HomeAI presets and mode profiles."""
from __future__ import annotations

import os
import re
import time

from .hfcore import strip_repo_suffix
from .modes import MODES, preset_for
from .util import read_json, write_json

STATE_FILE = "install.json"


def paths(root):
    return {
        "root": root, "state": os.path.join(root, STATE_FILE), "engine": os.path.join(root, "engine"),
        "ini": os.path.join(root, "engine", "models.ini"), "models": os.path.join(root, "models"),
        "homeai": os.path.join(root, "homeai"), "data": os.path.join(root, "homeai", "data"),
        "kit": os.path.join(root, "kit"), "extras": os.path.join(root, "extras"), "cache": os.path.join(root, "kit", "cache"),
    }


def load_state(root):
    return read_json(paths(root)["state"], None)


def save_state(root, st):
    st["updated"] = time.strftime("%Y-%m-%d")
    write_json(paths(root)["state"], st)


def new_state(root, hw, prefs):
    hw_keep = {k: hw.get(k) for k in ("os", "arch", "backend", "ram_gib", "vram_gib", "cpu_threads")}
    hw_keep["gpu_vendor"] = (hw.get("gpu") or {}).get("vendor")
    hw_keep["gpu_driver"] = (hw.get("gpu") or {}).get("driver")
    return {"kit_version": "1.0.0", "root": root, "hw": hw_keep, "prefs": prefs, "llama": {}, "models": {},
            "modes": {}, "components": {}, "shortcuts": [], "created": time.strftime("%Y-%m-%d")}


def section_name(choice, vision):
    base = strip_repo_suffix(choice["repo"].split("/", 1)[1])
    base = re.sub(r"(?i)[-_.]gguf$", "", base)
    name = "%s-%s%s" % (base, choice["quant"].replace(" ", "").replace("(", "").replace(")", ""), "-vision" if vision else "")
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-")[:90]


def model_dir(root, repo):
    return os.path.join(paths(root)["models"], re.sub(r"[^A-Za-z0-9._-]+", "_", repo.replace("/", "__")))


class BadChoice(ValueError):
    """A model suggestion that is missing the data needed to download and register it."""


def check_choice(choice, mode_key=None):
    """Raise BadChoice with a plain-language reason unless `choice` has a repo, a quant and at least one file path
    (and, for a vision mode, a usable mmproj entry when one is given)."""
    if not isinstance(choice, dict):
        raise BadChoice("the model suggestion is empty or unreadable - search again")
    repo = choice.get("repo")
    if not isinstance(repo, str) or repo.count("/") != 1 or not all(repo.split("/")):
        raise BadChoice("the model suggestion has no valid Hugging Face repo name - search again")
    if not isinstance(choice.get("quant"), str) or not choice["quant"].strip():
        raise BadChoice("the suggestion for %s does not say which quant to use - search again" % repo)
    files = choice.get("files")
    if not isinstance(files, list) or not files:
        raise BadChoice("the suggestion for %s lists no model files - search again or pick another" % repo)
    for f in files:
        if not isinstance(f, dict) or not isinstance(f.get("path"), str) or not f["path"].strip() \
                or not f["path"].lower().endswith(".gguf"):
            raise BadChoice("the suggestion for %s has an incomplete file list - search again or pick another" % repo)
    mm = choice.get("mmproj")
    if mm and mode_key and MODES.get(mode_key, {}).get("vision"):
        if not isinstance(mm, dict) or not isinstance(mm.get("path"), str) or not mm["path"].strip():
            raise BadChoice("the image-encoder (mmproj) entry for %s is incomplete - search again" % repo)
    return choice


def register_model(st, root, choice, mode_key):
    """Add a downloaded choice to the state as a models.ini section; returns the section name."""
    check_choice(choice, mode_key)
    vision = bool(choice.get("mmproj")) and bool(MODES[mode_key].get("vision"))
    sec = section_name(choice, vision)
    d = model_dir(root, choice["repo"])
    first = sorted(f["path"] for f in choice["files"])[0].rsplit("/", 1)[-1]
    try:
        ctx = int(choice.get("ctx") or st["prefs"].get("ctx", 32768))
        n_cpu_moe = int(choice.get("n_cpu_moe") or 0)
    except (TypeError, ValueError):
        raise BadChoice("the suggestion for %s has an unreadable context size - search again" % choice["repo"])
    entry = {"repo": choice["repo"], "quant": choice["quant"], "model": os.path.join(d, first),
             "files": [os.path.join(d, f["path"].rsplit("/", 1)[-1]) for f in choice["files"]],
             "ctx": ctx, "n_cpu_moe": n_cpu_moe,
             "params_b": choice.get("params_b"), "url": choice.get("url"), "thinking": bool(choice.get("thinking"))}
    if vision:
        entry["mmproj"] = os.path.join(d, choice["mmproj"]["path"].rsplit("/", 1)[-1])
        entry["files"].append(entry["mmproj"])
    old = st["models"].get(sec)
    if old:
        entry["ctx"] = max(entry["ctx"], old.get("ctx", 0))
    st["models"][sec] = entry
    return sec


def set_mode(st, mode_key, section):
    m = st["models"].get(section) or {}
    st["modes"][mode_key] = {"section": section, "label": MODES[mode_key]["label"], "ctx": m.get("ctx", 0)}


def models_ini_text(st):
    gpu = st["hw"].get("backend") != "cpu"
    out = ["version = 1", "",
           "; Written by the HomeAI Setup Kit. One [section] per model; the section name is the model id HomeAI shows.",
           "; Keys are llama-server option names without the leading dashes. Edit freely; re-running 'Add mode' only adds sections.",
           "; llama-server fits each model to your memory automatically (--fit is on by default).", "",
           "[*]", "parallel = 1", "jinja = true", ""]
    for sec, m in sorted(st["models"].items()):
        out.append("[%s]" % sec)
        out.append("model = %s" % m["model"])
        if m.get("mmproj"):
            out.append("mmproj = %s" % m["mmproj"])
        if not gpu:
            out.append("n-gpu-layers = 0")
        elif m.get("n_cpu_moe"):
            out.append("n-cpu-moe = %d" % m["n_cpu_moe"])
        out += ["ctx-size = %d" % m["ctx"], "flash-attn = on", "cache-type-k = q8_0", "cache-type-v = q8_0",
                "temp = 0.7", "top-p = 0.95", "top-k = 40", "min-p = 0.05", ""]
    return "\n".join(out)


def write_models_ini(root, st):
    p = paths(root)["ini"]
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(models_ini_text(st))
    os.replace(tmp, p)
    return p


def profiles(st):
    out = []
    for key, mm in st["modes"].items():
        m = st["models"].get(mm["section"]) or {}
        label = "%s (%s)" % (MODES[key]["label"], mm["section"])
        out.append({"key": key, "label": label, "id": mm["section"], "pattern": mm["section"].lower(), "ctx": m.get("ctx", 0),
                    "note": "%s%s" % ("%gB " % m["params_b"] if m.get("params_b") else "", m.get("quant", ""))})
    return out


def write_homeai_data(root, st):
    """data/installed.json (profiles for the router), presets.json (one button per installed mode), settings.json."""
    p = paths(root)
    os.makedirs(p["data"], exist_ok=True)
    write_json(os.path.join(p["data"], "installed.json"),
               {"profiles": profiles(st), "modes": sorted(st["modes"]), "backend": st["hw"].get("backend")})
    pp = os.path.join(p["data"], "presets.json")
    presets = read_json(pp, None)
    presets = presets if isinstance(presets, list) else []
    have = {x.get("id") for x in presets}
    md = {"temperature": False, "top_p": True, "top_k": True, "min_p": True, "repeat_penalty": True}
    for key in ["general", "coding"] + sorted(k for k in st["modes"] if k not in ("general", "coding")):
        if key in st["modes"] and key not in have:
            pr = preset_for(key)
            pr["params"]["model_default"] = dict(md)
            presets.append(pr)
    write_json(pp, presets)
    sp = os.path.join(p["data"], "settings.json")
    if not os.path.exists(sp):
        write_json(sp, {"defaultPreset": "general", "presetsVersion": 3, "samplingVersion": 1})
