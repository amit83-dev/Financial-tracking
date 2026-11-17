#!/usr/bin/env python3
"""One-shot installer for claude-fallback (Windows / macOS / Linux, Python 3.8+).

  python3 install.py            interactive
  python3 install.py --check    only re-run the provider self-test
"""
import getpass
import json
import os
import re
import secrets
import shutil
import subprocess
import sys

SRC = os.path.dirname(os.path.abspath(__file__))
HOME = os.environ.get("CLAUDE_FALLBACK_HOME", os.path.join(os.path.expanduser("~"), ".claude-fallback"))
SETTINGS = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
sys.path.insert(0, SRC)
import router  # noqa: E402


def ask(prompt, secret=False):
    try:
        v = (getpass.getpass(prompt) if secret else input(prompt)).strip()
    except EOFError:
        v = ""
    return v


def version_key(model_id):
    return [int(x) for x in re.findall(r"\d+", model_id)] or [0]


def newest(ids, must, avoid=()):
    pool = [i for i in ids if re.search(must, i, re.I) and not any(re.search(a, i, re.I) for a in avoid)]
    return max(pool, key=version_key) if pool else None


def pick_models(cfg):
    """Fill tiers with the newest suitable model ids each provider actually offers."""
    bad = ("image", "tts", "live", "audio", "embed", "vision", "exp", "robotics", "computer", "customtools")
    found = {}
    for name in cfg["providers"]:
        if router.provider_enabled(cfg, name):
            try:
                found[name] = router.list_models(cfg, name)
                print("   %-10s %d models" % (name, len(found[name])))
            except Exception as e:
                print("   %-10s could not list models (%s) - keeping defaults" % (name, str(e)[:80]))
    chosen = {}
    g = found.get("gemini", [])
    chosen["g_pro"] = newest(g, r"pro", bad + ("lite",))
    chosen["g_flash"] = newest(g, r"flash", bad + ("lite",))
    chosen["g_lite"] = newest(g, r"flash-lite", bad) or chosen["g_flash"]
    c = found.get("copilot", [])
    chosen["c_sonnet"] = newest(c, r"sonnet") or newest(c, r"gpt-\d", ("mini", "codex", "nano"))
    chosen["c_haiku"] = newest(c, r"haiku|mini") or chosen["c_sonnet"]
    d = found.get("deepseek", [])
    chosen["d_main"] = newest(d, r"chat|flash|v\d") or (d[0] if d else None)
    o = found.get("openrouter", [])
    chosen["o_main"] = "deepseek/deepseek-chat" if o else None

    def tier(*pairs):
        return [p + ":" + m for p, m in pairs if m and p in found]

    cfg["tiers"] = {
        "background": tier(("gemini", chosen["g_lite"]), ("copilot", chosen["c_haiku"]), ("deepseek", chosen["d_main"])),
        "simple": tier(("gemini", chosen["g_flash"]), ("copilot", chosen["c_haiku"]), ("deepseek", chosen["d_main"])),
        "code": tier(("copilot", chosen["c_sonnet"]), ("gemini", chosen["g_pro"]), ("deepseek", chosen["d_main"]),
                     ("openrouter", chosen["o_main"])),
        "hard": tier(("gemini", chosen["g_pro"]), ("copilot", chosen["c_sonnet"]), ("deepseek", chosen["d_main"])),
        "long": tier(("gemini", chosen["g_pro"]), ("gemini", chosen["g_flash"])),
        "vision": tier(("gemini", chosen["g_pro"]), ("copilot", chosen["c_sonnet"])),
    }
    return cfg


def merge_hook():
    os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
    data = {}
    if os.path.exists(SETTINGS):
        shutil.copy(SETTINGS, SETTINGS + ".bak-claude-fallback")
        with open(SETTINGS, encoding="utf-8") as f:
            data = json.load(f)
    cmd = '"%s" "%s"' % (sys.executable, os.path.join(HOME, "handoff.py"))
    entries = data.setdefault("hooks", {}).setdefault("StopFailure", [])
    for e in entries:
        for h in e.get("hooks", []):
            if "handoff.py" in h.get("command", ""):
                h["command"] = cmd
                break
        else:
            continue
        break
    else:
        entries.append({"matcher": "rate_limit", "hooks": [{"type": "command", "command": cmd}]})
    with open(SETTINGS, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return cmd


def write_shims():
    bindir = os.path.join(HOME, "bin")
    os.makedirs(bindir, exist_ok=True)
    py = sys.executable
    if os.name == "nt":
        p = os.path.join(bindir, "keepgoing.cmd")
        open(p, "w").write('@echo off\r\n"%s" "%s" --here\r\n' % (py, os.path.join(HOME, "handoff.py")))
    else:
        p = os.path.join(bindir, "keepgoing")
        open(p, "w").write('#!/bin/sh\nexec "%s" "%s" --here\n' % (py, os.path.join(HOME, "handoff.py")))
        os.chmod(p, 0o755)
    return bindir


def main():
    if "--check" in sys.argv:
        return router.selftest()
    print("== claude-fallback installer ==\n")
    if not shutil.which("claude"):
        print("! `claude` was not found on PATH - install Claude Code first.")
    os.makedirs(HOME, exist_ok=True)
    for f in ("router.py", "handoff.py"):
        shutil.copy(os.path.join(SRC, f), os.path.join(HOME, f))

    cfg = {}
    if os.path.exists(router.CONFIG_PATH):
        cfg = json.load(open(router.CONFIG_PATH, encoding="utf-8"))
    cfg = router.deep_merge(router.DEFAULT_CONFIG, cfg)
    cfg["router_token"] = cfg.get("router_token") or secrets.token_hex(24)

    print("1) Gemini - free key from https://aistudio.google.com/apikey")
    k = os.environ.get("GEMINI_API_KEY") or ask("   Gemini API key (Enter to skip): ", True)
    if k:
        cfg["providers"]["gemini"]["api_key"] = k

    print("\n2) GitHub Copilot - uses your Copilot subscription through the unofficial `copilot-api` proxy.")
    print("   NOTE: it is reverse-engineered and not supported by GitHub; heavy automated use may trigger abuse detection.")
    if shutil.which("npx") and ask("   Enable Copilot? [y/N]: ").lower().startswith("y"):
        print("   Opening GitHub device login (one time)...")
        subprocess.call(["npx.cmd" if os.name == "nt" else "npx", "--yes", "copilot-api@latest", "auth"])
        cfg["providers"]["copilot"]["enabled"] = True
        acct = ask("   Copilot plan: individual / business / enterprise [individual]: ") or "individual"
        cfg["providers"]["copilot"]["account_type"] = acct
        router.log("copilot account type: " + acct)
    elif not shutil.which("npx"):
        print("   Node.js (npx) not found - skipping Copilot. Install Node 20+ and re-run to add it.")

    print("\n3) Optional extras (Enter to skip)")
    k = ask("   DeepSeek API key: ", True)
    if k:
        cfg["providers"]["deepseek"]["api_key"] = k
    k = ask("   OpenRouter API key: ", True)
    if k:
        cfg["providers"]["openrouter"]["api_key"] = k

    print("\n4) Choosing the best model per task from what your accounts offer...")
    if cfg["providers"]["copilot"].get("enabled"):
        router.ensure_copilot(cfg)
        import time
        for _ in range(40):
            if router.port_open("127.0.0.1", 4141):
                break
            time.sleep(0.5)
    cfg = pick_models(cfg)
    with open(router.CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.chmod(router.CONFIG_PATH, 0o600) if os.name != "nt" else None
    router._cfg_cache["cfg"] = None
    for t, c in cfg["tiers"].items():
        print("   %-10s %s" % (t, " > ".join(c) or "(no provider)"))

    print("\n5) Registering the automatic hand-off hook in ~/.claude/settings.json (backup saved)...")
    print("   " + merge_hook())
    bindir = write_shims()

    print("\n6) Testing each provider...")
    rc = router.selftest()
    print("\nDone. Open a NEW Claude Code window so it reads the hook.")
    print("When the usage limit hits, a new terminal opens in the same folder and continues the conversation.")
    print("Manual fallback any time: run `keepgoing` (add %s to PATH)." % bindir)
    print("Config: %s   Log: %s" % (router.CONFIG_PATH, router.LOG_PATH))
    return rc


if __name__ == "__main__":
    sys.exit(main())
