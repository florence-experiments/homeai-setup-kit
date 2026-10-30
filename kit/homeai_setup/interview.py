"""Plain-English questions. Every question has numbered answers and a sensible default (just press Enter)."""
from __future__ import annotations

import os

from .modes import MODES, OPTIONAL_MODES
from .util import IS_WIN, default_install_dir, say


def choose(ask, key, title, options, default=1, multi=False):
    """options: list of (value, text). Returns the value (or a list of values when multi)."""
    say("")
    say(title)
    for i, (_, text) in enumerate(options, 1):
        say("   %d) %s" % (i, text))
    hint = ("numbers separated by commas, 0 = none" if multi else "a number") + (", Enter = %s" % default if default != "" else "")
    while True:
        raw = ask.ask(key, "   Your choice (%s): " % hint, default)
        parts = [p.strip() for p in str(raw).replace(" ", ",").split(",") if p.strip()]
        try:
            nums = [int(p) for p in parts]
        except ValueError:
            nums = None
        if multi and nums == [0]:
            return []
        if nums and all(1 <= n <= len(options) for n in nums) and (multi or len(nums) == 1):
            vals = [options[n - 1][0] for n in nums]
            return vals if multi else vals[0]
        say("   Please type %s." % ("one or more of the numbers above" if multi else "one of the numbers above"))
        if ask.scripted:
            raise ValueError("invalid scripted answer for %s: %r" % (key, raw))


def interview(ask, hw):
    say("")
    say("=" * 70)
    say(" A few questions (press Enter to accept the suggestion in brackets)")
    say("=" * 70)
    p = {}
    extra = [k for k in OPTIONAL_MODES]
    p["extra_modes"] = choose(ask, "uses",
                              "1. HomeAI always gets two modes: General (everyday chat) and Coding.\n"
                              "   Which other things will you use it for? You can also add these later with '+ Add mode'.",
                              [(k, "%s - %s" % (MODES[k]["label"], MODES[k]["desc"])) for k in extra], default=0, multi=True)
    ram = hw.get("ram_gib", 8)
    sug_ctx = 1 if (hw.get("backend") == "cpu" and ram < 24) else 2
    p["ctx"] = choose(ask, "ctx",
                      "2. How much should the AI remember at once (its 'context')?",
                      [(8192, "Short - a few pages (about 6,000 words). Uses the least memory."),
                       (32768, "Medium - a long chat or a report (about 24,000 words). Recommended."),
                       (65536, "Long - a book chapter or many files (about 48,000 words). Needs more memory.")], default=sug_ctx)
    p["speed"] = choose(ask, "speed",
                        "3. Speed or quality?",
                        [("fast", "Fast answers (smaller models)"),
                         ("balanced", "Balanced (recommended)"),
                         ("quality", "Best quality (bigger models, slower)")], default=2)
    p["uncensored"] = choose(ask, "uncensored",
                             "4. Which kind of models?",
                             [(True, "Uncensored / abliterated - answers without moralising or refusing (default)"),
                              (False, "Standard - the makers' original models with their usual safety tuning")], default=1)
    free = hw.get("disk_free_gib", 100)
    opts = [(b, "%d GB" % b) for b in (20, 50, 100, 200) if b < free - 5]
    opts.append((max(5, int(free - 10)), "Use most of the free space (%d GB)" % max(5, int(free - 10))))
    p["disk_budget_gib"] = choose(ask, "disk", "5. How much disk space may models use in total? (%.0f GB free)" % free,
                                  opts, default=min(2, len(opts)))
    comps = [("searxng", "Web search for HomeAI (SearXNG, private, needs Docker)"),
             ("voice", "Voice: talk to HomeAI and hear answers (about 1 GB extra)"),
             ("openhands", "OpenHands: an AI coding agent that works in a sandbox folder (needs Docker)"),
             ("updater", "Model Updater: checks Hugging Face for newer versions of your models")]
    if IS_WIN or hw.get("os") == "windows":
        comps.append(("security", "Security Monitor: watches for suspicious network/program activity (Windows, advanced)"))
    p["components"] = choose(ask, "components", "6. Optional extras (all can be added later by running setup again):",
                             comps, default=0, multi=True)
    dflt = default_install_dir()
    say("")
    say("7. Where should HomeAI be installed?")
    raw = ask.ask("folder", "   Folder (Enter = %s): " % dflt, dflt)
    p["install_dir"] = os.path.abspath(os.path.expanduser(raw.strip().strip('"')))
    say("")
    say("8. Hugging Face token (optional). Only needed for gated models; it is used for this session only and never saved.")
    p["_hf_token"] = ask.ask("hf_token", "   Paste a token or press Enter to skip: ", "").strip() or None
    p["shortcuts"] = choose(ask, "shortcuts", "9. Create shortcuts?",
                            [(True, "Yes - desktop and start-menu shortcuts"), (False, "No")], default=1)
    return p


def summary(p, hw):
    lines = ["  Modes      : General, Coding%s" % ("".join(", " + MODES[k]["label"] for k in p["extra_modes"])),
             "  Context    : %d tokens" % p["ctx"],
             "  Preference : %s, %s models" % (p["speed"], "uncensored" if p["uncensored"] else "standard"),
             "  Disk budget: %d GB for models" % p["disk_budget_gib"],
             "  Extras     : %s" % (", ".join(p["components"]) or "none"),
             "  Folder     : %s" % p["install_dir"],
             "  HF token   : %s" % ("given (this session only)" if p.get("_hf_token") else "none"),
             "  Shortcuts  : %s" % ("yes" if p["shortcuts"] else "no")]
    return "\n".join(lines)


def public_prefs(p):
    """What is remembered in install.json (never the token)."""
    return {k: v for k, v in p.items() if not k.startswith("_")}
