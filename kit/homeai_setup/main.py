# Built by Florence for the community.
"""HomeAI Setup Kit - the setup wizard.

  Windows: double-click Setup-Windows.cmd        Linux: ./setup-linux.sh
  Advanced: python -m homeai_setup.main [--answers answers.json] [--no-start]

Steps: 1) look at this computer (read-only)  2) ask what you need  3) search Hugging Face for models that fit
4) show exactly what will be downloaded  5) download and install ONLY after you type yes.
Everything local; no telemetry. Tokens only if the user provides an HF token (used for this session, never saved)."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

from . import addmode, components, configgen as C, hfsearch as S, interview as I, launchers, llamacpp, scan
from .modes import MODES
from .util import IS_WIN, PACKAGE_ROOT, Asker, is_yes, say

ENGINE_MB = {"cuda": 700, "vulkan": 60, "cpu": 40}
DOCS = ["README.md", "help.txt", "LICENSE", "DISCLAIMER.md", "THIRD_PARTY_NOTICES.md"]
SAFETY_NOTE = ("HomeAI always keeps one fixed rule that cannot be switched off: no sexual content involving anyone "
               "under 18. Nothing else is restricted by HomeAI itself.")


def banner():
    say("=" * 70)
    say(" HomeAI Setup Kit - a private AI that runs on this computer")
    say("=" * 70)
    say(" Everything local; no telemetry.")
    say(" Tokens only if the user provides an HF token.")
    say(" Nothing is downloaded until you have seen the list and typed yes.")
    say(" " + SAFETY_NOTE)
    say(" Experimental software, provided as-is with no warranty - see DISCLAIMER.md.")


def tiny_choice(hf, mode_key):
    """Test hook (HOMEAI_KIT_TEST_TINY=1): a 100 MB model so the whole flow can be tested quickly."""
    repo, path = "bartowski/SmolLM2-135M-Instruct-GGUF", "SmolLM2-135M-Instruct-Q4_K_M.gguf"
    f = next(x for x in hf.tree(repo) if x.get("path") == path)
    size, sha = (f.get("lfs") or {}).get("size") or f.get("size"), (f.get("lfs") or {}).get("oid")
    return {"mode": mode_key, "repo": repo, "url": "https://huggingface.co/" + repo, "name": "SmolLM2-135M-Instruct",
            "quant": "Q4_K_M", "bpw": 4.89, "params_b": 0.135, "active_b": None, "arch": "llama", "ctx": 4096,
            "files": [{"path": path, "sha256": sha, "size": size}], "size": size, "mmproj": None,
            "download_gib": round(size / 1024 ** 3, 2), "fit": {}, "n_cpu_moe": 0, "reasons": ["test model"],
            "warnings": [], "score": 0, "uncensored": False, "thinking": False}


def pick_models(ask, hw, prefs, modes, token, existing):
    hf = S.hf_client(os.path.join(PACKAGE_ROOT, "kit", "cache"), token)
    budget = float(prefs["disk_budget_gib"])
    picks = {}
    for key in modes:
        if existing and key in existing.get("modes", {}):
            say("\n%s mode is already installed (%s) - kept." % (MODES[key]["label"], existing["modes"][key]["section"]))
            continue
        say("\n" + "-" * 70)
        say(" %s mode: %s" % (MODES[key]["label"], MODES[key]["desc"]))
        say("-" * 70)
        if os.environ.get("HOMEAI_KIT_TEST_TINY"):
            res, errs = [tiny_choice(hf, key)], []
        else:
            res, errs = S.Searcher(hf, hw, dict(prefs, disk_budget_gib=max(1.0, budget)), say).run(key)
        options = []
        for i, ch in enumerate(res, 1):
            say(S.describe_choice(i, ch))
            options.append(ch)
        if not res:
            say("No suitable model found right now%s." % (" (" + "; ".join(errs) + ")" if errs else ""))
        seen = set()
        for k, ch in picks.items():
            if isinstance(ch, dict) and ch.get("repo") and (ch["repo"], ch["quant"]) not in seen and not (
                    MODES[key].get("vision") and not ch.get("mmproj")):
                seen.add((ch["repo"], ch["quant"]))
                options.append({"same_as": k})
                say("  %d) Use the same model as %s mode (no extra download)" % (len(options), MODES[k]["label"]))
        say("  0) Skip this mode (you can add it later with '+ Add mode')")
        while True:
            raw = ask.ask("pick_" + key, "Pick a number (Enter = 1): ", "1" if options else "0")
            try:
                n = int(raw)
            except ValueError:
                n = -1
            if 0 <= n <= len(options):
                break
            say("Please type one of the numbers shown.")
            if ask.scripted:
                n = 0
                break
        if n == 0:
            if key == "general":
                say("General mode is needed for HomeAI to work - setup will stop here. Nothing was downloaded.")
                return None
            continue
        ch = options[n - 1]
        if ch.get("same_as"):
            picks[key] = picks[ch["same_as"]]
        else:
            picks[key] = ch
            budget -= ch["download_gib"]
    return picks


def show_plan(hw, picks, comps, existing):
    say("\n" + "=" * 70)
    say(" What will be downloaded and installed")
    say("=" * 70)
    total = 0.0
    if not (existing and existing.get("llama")):
        mb = ENGINE_MB.get(hw["backend"], 60)
        say("  AI engine : llama.cpp (%s build) from github.com/ggml-org/llama.cpp, about %d MB, SHA-256 checked"
            % (hw["backend"].upper(), mb))
        total += mb / 1024
    if IS_WIN:
        say("  Python    : already downloaded by the setup launcher (copied into the HomeAI folder)")
    done = set()
    for key, ch in picks.items():
        tag = (ch["repo"], ch["quant"])
        if tag in done:
            say("  %-10s: (same model as above)" % MODES[key]["label"])
            continue
        done.add(tag)
        say("  %-10s: %s %s, %.2f GiB from huggingface.co, SHA-256 checked" % (MODES[key]["label"], ch["repo"], ch["quant"],
                                                                            ch["download_gib"]))
        total += ch["download_gib"]
    for c in comps:
        say("  Extra     : %s%s" % (components.DESCR[c], ", about %.1f GB" % components.SIZES_GB[c] if components.SIZES_GB[c] else ""))
        total += components.SIZES_GB[c]
    say("  Total     : about %.1f GB" % total)


def copy_runtime(root):
    """Windows: the setup launcher's Python goes into <root>/python so HomeAI never depends on another Python."""
    if not IS_WIN:
        return
    src, dst = sys.base_prefix, os.path.join(root, "python")
    if os.path.abspath(src) == os.path.abspath(dst) or os.path.isfile(os.path.join(dst, "python.exe")):
        return
    say("   copying Python into the HomeAI folder...")
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))


def install(root, hw, p, picks, token, existing):
    os.makedirs(root, exist_ok=True)
    copy_runtime(root)
    components.install_kit(root)
    st = existing or C.new_state(root, hw, I.public_prefs(p))
    st["prefs"] = I.public_prefs(p)
    if not IS_WIN:
        st["python"] = sys.executable
    C.save_state(root, st)
    say("\n[1/5] AI engine")
    if not st.get("llama") or st["llama"].get("backend") != hw["backend"]:
        info = llamacpp.install(os.path.join(root, "engine"), hw)
        st["llama"] = {"build": info["build"], "backend": info["backend"], "assets": info["assets"]}
        C.save_state(root, st)
    else:
        say("   already installed (%s)" % st["llama"]["build"])
    say("\n[2/5] HomeAI app")
    components.install_homeai(root)
    say("\n[3/5] Models")
    done = {}
    for key, ch in picks.items():
        tag = (ch["repo"], ch["quant"])
        done[tag] = addmode.apply(root, key, {"existing": done[tag]} if tag in done else ch, token)
    st = C.load_state(root)
    C.write_models_ini(root, st)
    C.write_homeai_data(root, st)
    say("\n[4/5] Extras")
    failed = []
    for c in p["components"]:
        try:
            components.INSTALLERS[c](root)
            st = C.load_state(root)
            st.setdefault("components", {})[c] = True
            C.save_state(root, st)
        except Exception as ex:  # one extra failing must not break the rest
            failed.append(c)
            say("   %s could not be installed: %s (run setup again later to retry)" % (c, ex))
    say("\n[5/5] Launchers and shortcuts")
    st = C.load_state(root)
    comps = [c for c, on in (st.get("components") or {}).items() if on]
    scripts = launchers.write_scripts(root, comps)
    if p["shortcuts"]:
        st["shortcuts"] = sorted(set(st.get("shortcuts", []) + launchers.make_shortcuts(root, scripts)))
    for d in DOCS:
        s = os.path.join(PACKAGE_ROOT, d)
        if os.path.isfile(s):
            shutil.copy2(s, os.path.join(root, d))
    C.save_state(root, st)
    return failed


def main(argv=None):
    ap = argparse.ArgumentParser(description="HomeAI Setup Kit")
    ap.add_argument("--answers", help="JSON file with answers (for testing / unattended installs)")
    ap.add_argument("--no-start", action="store_true", help="do not start HomeAI at the end")
    a = ap.parse_args(argv)
    answers = None
    if a.answers:
        try:
            with open(a.answers, encoding="utf-8-sig") as f:
                answers = json.load(f)
        except (OSError, ValueError) as ex:
            say("Could not read the answers file %s: %s" % (a.answers, ex))
            return 2
        if not isinstance(answers, dict):
            say("The answers file %s must hold a JSON object ({...})" % a.answers)
            return 2
    ask = Asker(answers)
    banner()
    say("")
    hw = scan.scan()
    say(scan.describe(hw))
    if hw["os"] not in ("windows", "linux"):
        say("Sorry, this kit supports Windows and Linux only.")
        return 2
    p = I.interview(ask, hw)
    root = p["install_dir"]
    token = p.pop("_hf_token", None) or os.environ.get("HF_TOKEN") or None
    existing = C.load_state(root)
    if existing:
        say("\nHomeAI is already installed in %s - your chats, models and settings are kept; setup will add or repair." % root)
    hw2 = scan.scan(root) if root else hw
    hw["disk_free_gib"] = hw2.get("disk_free_gib", hw.get("disk_free_gib"))
    if hw.get("disk_free_gib", 0) < 3:
        say("Less than 3 GB free on that drive - please free some space or pick another folder.")
        return 2
    modes = ["general", "coding"] + [m for m in p["extra_modes"] if m not in ("general", "coding")]
    say("\n" + I.summary(dict(p, _hf_token=token), hw))
    picks = pick_models(ask, hw, I.public_prefs(p), modes, token, existing)
    if picks is None:
        return 1
    show_plan(hw, picks, p["components"], existing)
    if not is_yes(ask.ask("confirm", "\nType yes to download and install (anything else cancels): ", "")):
        say("Cancelled - nothing was downloaded or installed.")
        return 0
    failed = install(root, hw, p, picks, token, existing)
    say("\n" + "=" * 70)
    say(" Done! HomeAI is installed in %s" % root)
    say(" Start it with: %s" % ("the 'HomeAI' shortcut or 'Start HomeAI.cmd'" if IS_WIN else "./start-homeai.sh (or the HomeAI menu entry)"))
    say(" Then open http://127.0.0.1:8090/ in your browser. Add more modes with '+ Add mode'.")
    if failed:
        say(" Some extras were not installed: %s - run setup again to retry." % ", ".join(failed))
    say("=" * 70)
    if not a.no_start and I.choose(ask, "start", "Start HomeAI now?", [(True, "Yes"), (False, "No")], default=1):
        from . import control
        control.start(root)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        say("\nCancelled.")
        sys.exit(1)
