# Built by Florence for the community.
"""HomeAI Model Updater: checks Hugging Face for newer or better models for each HomeAI mode you have installed.

  Windows: double-click "Model Updater" (or extras\\model-updater\\Run-Model-Updater.cmd)
  Linux:   ./extras/model-updater/run-model-updater.sh

It uses the same search as setup (GGUF only, best quant that fits, memory check, vision files, refusal evidence).
Nothing is downloaded or changed unless you type yes. Every swap can be undone (option 'u'), and old model files are
only deleted when you say so, one by one."""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "kit"))

from homeai_setup import addmode, configgen as C, hfsearch as S  # noqa: E402
from homeai_setup.modes import MODES  # noqa: E402
from homeai_setup.util import Asker, is_yes, say  # noqa: E402


def reload_engine():
    import urllib.request
    try:
        urllib.request.urlopen("http://127.0.0.1:8081/models?reload=1", timeout=10).read()
    except Exception:
        pass


def check(token, ask):
    st = C.load_state(ROOT)
    if not st or not st.get("modes"):
        say("HomeAI is not set up in %s yet." % ROOT)
        return
    found = []
    for key, mm in sorted(st["modes"].items()):
        say("\nChecking %s mode (now: %s)..." % (MODES[key]["label"], mm["section"]))
        r = addmode.search_mode(ROOT, key, token)
        for e in r["errors"]:
            say("  note: " + e)
        cur = st["models"].get(mm["section"]) or {}
        best = None
        for ch in r["choices"]:
            sec = C.section_name(ch, bool(ch.get("mmproj")) and bool(MODES[key].get("vision")))
            if sec != mm["section"] and not (ch["repo"] == cur.get("repo") and ch["quant"] == cur.get("quant")):
                best = ch
                break
            if sec == mm["section"]:
                break
        if best:
            say("  Suggested:")
            say(S.describe_choice(1, best))
            found.append((key, best))
        else:
            say("  Your current model is still the best match.")
    if not found:
        say("\nEverything is up to date.")
        return
    for key, ch in found:
        say("")
        a = ask.ask("swap_" + key, "Switch %s mode to %s %s? This downloads it. Type yes to confirm, Enter to skip: "
                    % (MODES[key]["label"], ch["repo"], ch["quant"]), "")
        if not is_yes(a):
            say("  Skipped.")
            continue
        prev = C.load_state(ROOT)["modes"][key]["section"]
        sec = addmode.apply(ROOT, key, ch, token)
        st = C.load_state(ROOT)
        st.setdefault("updater_history", []).append({"mode": key, "previous": prev, "new": sec, "date": time.strftime("%Y-%m-%d")})
        C.save_state(ROOT, st)
        reload_engine()
        say("  Done. The previous model is kept, so you can undo this.")


def undo(ask):
    st = C.load_state(ROOT)
    hist = st.get("updater_history") or []
    if not hist:
        say("Nothing to undo.")
        return
    h = hist[-1]
    if h["previous"] not in st["models"]:
        say("The previous model (%s) was deleted, so this cannot be undone." % h["previous"])
        return
    if is_yes(ask.ask("undo", "Put %s mode back to %s? Type yes: " % (MODES[h["mode"]]["label"], h["previous"]), "")):
        addmode.apply(ROOT, h["mode"], {"existing": h["previous"]})
        st = C.load_state(ROOT)
        st["updater_history"] = hist[:-1]
        C.save_state(ROOT, st)
        reload_engine()
        say("Undone.")


def cleanup(ask):
    st = C.load_state(ROOT)
    used = {mm["section"] for mm in st["modes"].values()}
    unused = [s for s in sorted(st["models"]) if s not in used]
    if not unused:
        say("No unused models.")
        return
    for sec in unused:
        m = st["models"][sec]
        size = sum(os.path.getsize(f) for f in m.get("files", []) if os.path.isfile(f)) / 1024 ** 3
        if not is_yes(ask.ask("del_" + sec, "Delete unused model %s (%.1f GB)? Type yes to delete: " % (sec, size), "")):
            continue
        for f in m.get("files", []):
            try:
                os.remove(f)
            except OSError:
                pass
        d = os.path.dirname(m["model"])
        try:
            os.rmdir(d)
        except OSError:
            pass
        del st["models"][sec]
        st["updater_history"] = [h for h in st.get("updater_history", []) if h["previous"] != sec]
        say("  Deleted.")
    C.save_state(ROOT, st)
    C.write_models_ini(ROOT, st)
    reload_engine()


def main():
    ans = None
    if "--answers" in sys.argv:
        import json
        with open(sys.argv[sys.argv.index("--answers") + 1], encoding="utf-8") as f:
            ans = json.load(f)
    ask = Asker(ans)
    token = os.environ.get("HF_TOKEN") or None
    say("HomeAI Model Updater - nothing changes unless you type yes.")
    while True:
        say("\n  c) Check for better models\n  u) Undo the last switch\n  d) Delete models no mode uses\n  q) Quit")
        a = ask.ask("menu", "Choice (Enter = c): ", "c").strip().lower()
        if a in ("q", "quit", "exit"):
            return
        if a == "u":
            undo(ask)
        elif a == "d":
            cleanup(ask)
        else:
            check(token, ask)
            return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    if os.name == "nt" and sys.stdin.isatty():
        input("\nPress Enter to close.")
