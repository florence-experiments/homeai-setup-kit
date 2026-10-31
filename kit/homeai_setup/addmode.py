"""Add a mode: search Hugging Face, let the user pick, download after they type yes, wire it into HomeAI.

Used three ways: by the setup wizard, from the command line (python -m homeai_setup.addmode <mode>), and by the
HomeAI server for the '+ Add mode' button (search_mode / apply in a background job)."""
from __future__ import annotations

import argparse
import os
import sys

from . import configgen as C
from . import hfcore as H
from . import hfsearch as S
from .modes import MODES
from .util import Asker, gib, is_yes, say


def hw_from_state(st):
    h = st["hw"]
    return {"os": h.get("os"), "backend": h.get("backend"), "gpu": {"vendor": h.get("gpu_vendor"), "driver": h.get("gpu_driver")},
            "vram_gib": h.get("vram_gib") or 0, "ram_gib": h.get("ram_gib") or 8}


def used_gib(st):
    tot = 0
    for m in st["models"].values():
        for f in m.get("files", []):
            try:
                tot += os.path.getsize(f)
            except OSError:
                pass
    return gib(tot)


def search_mode(root, mode_key, token=None, log=say, prefs_override=None):
    st = C.load_state(root)
    prefs = dict(st["prefs"], **(prefs_override or {}))
    prefs["disk_budget_gib"] = max(1.0, float(prefs.get("disk_budget_gib", 50)) - used_gib(st))
    hf = S.hf_client(C.paths(root)["cache"], token)
    res, errs = S.Searcher(hf, hw_from_state(st), prefs, log).run(mode_key)
    existing = []
    for sec, m in sorted(st["models"].items()):
        if MODES[mode_key].get("vision") and not m.get("mmproj"):
            continue
        existing.append({"section": sec, "repo": m.get("repo"), "quant": m.get("quant")})
    return {"mode": mode_key, "choices": res, "existing": existing, "errors": errs}


def apply(root, mode_key, pick, token=None, log=say):
    """pick = a choice dict from search_mode, or {'existing': section}. Downloads (resumable, SHA-256 checked)."""
    st = C.load_state(root)
    if pick.get("existing"):
        sec = pick["existing"]
        if sec not in st["models"]:
            raise ValueError("unknown model section %s" % sec)
    else:
        C.check_choice(pick, mode_key)            # clear message instead of a KeyError / IndexError later
        hf = S.hf_client(C.paths(root)["cache"], token)
        S.fill_sizes(hf, pick)
        dest = C.model_dir(root, pick["repo"])
        items = list(pick["files"]) + ([pick["mmproj"]] if pick.get("mmproj") and MODES[mode_key].get("vision") else [])
        for f in items:
            name = f["path"].rsplit("/", 1)[-1]
            log("Downloading %s (%s)..." % (name, "%.2f GiB" % gib(f["size"]) if f.get("size") else "size not listed"))
            ok, got = H.download_file(hf, pick["repo"], f["path"], dest, f.get("size"), f.get("sha256"))
            if not ok or not got or not os.path.isfile(got):
                raise RuntimeError("download of %s failed or could not be verified (see the messages above). "
                                   "Nothing was switched over; run Add mode again to retry." % name)
        sec = C.register_model(st, root, pick, mode_key)
    C.set_mode(st, mode_key, sec)
    C.save_state(root, st)
    C.write_models_ini(root, st)
    C.write_homeai_data(root, st)
    log("%s mode is ready (model: %s)." % (MODES[mode_key]["label"], sec))
    return sec


def interactive(root, mode_key, ask, token=None, allow_reuse=True):
    """Console flow. Returns the section used, or None when skipped."""
    say("")
    say("-" * 70)
    say(" %s mode: %s" % (MODES[mode_key]["label"], MODES[mode_key]["desc"]))
    say("-" * 70)
    r = search_mode(root, mode_key, token)
    options = []
    if r["choices"]:
        say("Suggestions (best first):")
        for i, ch in enumerate(r["choices"], 1):
            say(S.describe_choice(i, ch))
            options.append(ch)
    else:
        say("No suitable model was found right now%s." % (" (" + "; ".join(r["errors"]) + ")" if r["errors"] else ""))
    reuse = r["existing"] if allow_reuse else []
    for j, e in enumerate(reuse, len(options) + 1):
        say("  %d) Use a model you already have: %s" % (j, e["section"]))
        options.append({"existing": e["section"]})
    if not options:
        return None
    say("  0) Skip this mode for now")
    while True:
        raw = ask.ask("pick_" + mode_key, "Pick a number (Enter = 1): ", "1")
        try:
            n = int(raw)
        except ValueError:
            n = -1
        if n == 0:
            return None
        if 1 <= n <= len(options):
            break
        say("Please type one of the numbers shown.")
        if ask.scripted:
            return None
    pick = options[n - 1]
    if not pick.get("existing"):
        say("This will download %.2f GiB from %s" % (pick["download_gib"], pick["url"]))
        if not is_yes(ask.ask("confirm_" + mode_key, "Type yes to download, anything else to skip: ", "")):
            say("Skipped - nothing was downloaded.")
            return None
    try:
        return apply(root, mode_key, pick, token)
    except (ValueError, RuntimeError) as ex:      # bad suggestion data or a failed / unverified download
        say("Could not set up %s mode: %s" % (MODES[mode_key]["label"], ex))
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Add a HomeAI mode (search Hugging Face and download a model for it).")
    ap.add_argument("mode", nargs="?", choices=sorted(MODES))
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    a = ap.parse_args(argv)
    if not C.load_state(a.root):
        say("No HomeAI installation found in %s" % a.root)
        return 2
    if not a.mode:
        st = C.load_state(a.root)
        keys = sorted(MODES, key=lambda k: (k not in ("general", "coding"), MODES[k]["label"]))
        say("Which mode would you like to add or change?")
        for i, k in enumerate(keys, 1):
            say("  %2d) %-14s %s%s" % (i, MODES[k]["label"], MODES[k]["desc"], "  [installed]" if k in st["modes"] else ""))
        raw = Asker().ask("mode", "Number (Enter = cancel): ", "")
        try:
            a.mode = keys[int(raw) - 1]
        except (ValueError, IndexError):
            return 0
    token = None
    if sys.stdin.isatty():
        try:
            token = input("Hugging Face token (optional, Enter to skip): ").strip() or None
        except EOFError:
            token = None
    sec = interactive(a.root, a.mode, Asker(), token)
    if sec:
        try:
            import urllib.request
            urllib.request.urlopen("http://127.0.0.1:8081/models?reload=1", timeout=10).read()
            say("The AI engine has picked up the change. Reload the HomeAI page (F5) to see the new mode.")
        except Exception:
            say("Start HomeAI (or reload the page if it is running) to use the new mode.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
