#!/usr/bin/env python3
"""Hook for Claude Code's StopFailure event (matcher: rate_limit).

When the subscription limit stops a turn, this makes sure the local router is
running and opens a NEW terminal window in the same folder that continues the
same conversation (`claude --continue`) through the router.

Run by hand with --here to do the same in the current terminal.
"""
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import time

HOME = os.environ.get("CLAUDE_FALLBACK_HOME", os.path.join(os.path.expanduser("~"), ".claude-fallback"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HOME)
import router  # noqa: E402

DEBOUNCE_SECONDS = 30 * 60
PROMPT = "The usage limit was reached, so you are now running on a fallback model. Continue the task from where you stopped."


def log(msg):
    router.log("handoff: " + msg)


def ensure_router(cfg):
    host, port = cfg["listen_host"], cfg["listen_port"]
    if router.port_open(host, port):
        return True
    script = os.path.join(HOME, "router.py")
    if not os.path.exists(script):
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "router.py")
    kw = {"creationflags": 0x00000008 | 0x00000200} if os.name == "nt" else {"start_new_session": True}
    subprocess.Popen([sys.executable, script, "serve"], stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)
    for _ in range(40):
        time.sleep(0.25)
        if router.port_open(host, port):
            return True
    return False


def env_for(cfg):
    return {
        "ANTHROPIC_BASE_URL": "http://%s:%d" % (cfg["listen_host"], cfg["listen_port"]),
        "ANTHROPIC_AUTH_TOKEN": cfg.get("router_token") or "local",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    }


def write_launcher(cwd, cfg):
    os.makedirs(HOME, exist_ok=True)
    env = env_for(cfg)
    if os.name == "nt":
        path = os.path.join(HOME, "resume.cmd")
        lines = ["@echo off", 'cd /d "%s"' % cwd]
        lines += ['set "%s=%s"' % kv for kv in env.items()]
        lines += ["echo [claude-fallback] continuing on a fallback model via the local router",
                  'claude --continue "%s"' % PROMPT, "echo.", "echo (session ended - close this window)", "pause"]
        data = "\r\n".join(lines) + "\r\n"
    else:
        path = os.path.join(HOME, "resume.sh")
        lines = ["#!/usr/bin/env bash", "cd %s || exit 1" % shlex.quote(cwd)]
        lines += ["export %s=%s" % (k, shlex.quote(v)) for k, v in env.items()]
        lines += ["echo '[claude-fallback] continuing on a fallback model via the local router'",
                  "claude --continue %s" % shlex.quote(PROMPT),
                  'exec "${SHELL:-bash}"']
        data = "\n".join(lines) + "\n"
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(data)
    if os.name != "nt":
        os.chmod(path, 0o700)
    return path


def open_terminal(script):
    if os.name == "nt":
        subprocess.Popen(["cmd", "/k", script], creationflags=subprocess.CREATE_NEW_CONSOLE)
        return "windows console"
    if sys.platform == "darwin":
        osa = 'tell application "Terminal" to do script "bash %s"\ntell application "Terminal" to activate' % script.replace('"', '\\"')
        subprocess.Popen(["osascript", "-e", osa])
        return "macOS Terminal"
    try:
        if "microsoft" in open("/proc/version").read().lower() and shutil.which("cmd.exe"):
            subprocess.Popen(["cmd.exe", "/c", "start", "wsl.exe", "bash", script])
            return "WSL window"
    except OSError:
        pass
    for exe, args in (("x-terminal-emulator", ["-e"]), ("gnome-terminal", ["--"]), ("konsole", ["-e"]),
                      ("xfce4-terminal", ["-x"]), ("kitty", []), ("alacritty", ["-e"]), ("xterm", ["-e"])):
        if shutil.which(exe):
            subprocess.Popen([exe] + args + ["bash", script], stdin=subprocess.DEVNULL)
            return exe
    return None


def debounced(cwd):
    state = os.path.join(HOME, "handoff-state.json")
    try:
        data = json.load(open(state))
    except (OSError, ValueError):
        data = {}
    key = hashlib.sha1(cwd.encode()).hexdigest()
    now = time.time()
    if now - data.get(key, 0) < DEBOUNCE_SECONDS:
        return True
    data[key] = now
    try:
        json.dump(data, open(state, "w"))
    except OSError:
        pass
    return False


def main():
    here = "--here" in sys.argv
    cfg = router.get_config()
    if here:
        cwd = os.getcwd()
    else:
        if os.environ.get("CLAUDE_FALLBACK_AUTO", "1") == "0":
            return 0
        try:
            payload = json.load(sys.stdin)
        except ValueError:
            payload = {}
        log("hook payload: %s" % json.dumps(payload)[:400])
        # ignore events coming from a session that is already on the fallback
        if os.environ.get("ANTHROPIC_BASE_URL", "").startswith("http://%s:%d" % (cfg["listen_host"], cfg["listen_port"])):
            log("already running on fallback; skipping")
            return 0
        cwd = payload.get("cwd") or os.getcwd()
        if debounced(cwd):
            log("debounced for %s" % cwd)
            return 0
    if not ensure_router(cfg):
        log("router did not start")
        print("claude-fallback: router did not start (see %s)" % router.LOG_PATH, file=sys.stderr)
        return 0
    script = write_launcher(cwd, cfg)
    if here:
        if os.name == "nt":
            return subprocess.call(["cmd", "/c", script])
        os.execvp("bash", ["bash", script])
    how = open_terminal(script)
    log("opened %s in %s" % (how, cwd) if how else "no terminal found; run: %s" % script)
    if not how:
        print("claude-fallback: no terminal found. Run `keepgoing` in your project folder.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
