#!/usr/bin/env python3
"""claude-fallback router.

A tiny local gateway that speaks Anthropic's Messages API to Claude Code and
forwards each request to the best available provider for the task:

  * Gemini      (OpenAI-compatible endpoint, translated here)
  * GitHub Copilot (through the `copilot-api` proxy, Anthropic-compatible)
  * DeepSeek / OpenRouter (Anthropic-compatible endpoints)

Per request it classifies the task (background / simple / code / hard / long /
vision), picks the ordered candidate list for that tier, and fails over to the
next candidate on any error. Standard library only.

Usage:  router.py serve | models | selftest
"""
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOME = os.environ.get("CLAUDE_FALLBACK_HOME", os.path.join(os.path.expanduser("~"), ".claude-fallback"))
CONFIG_PATH = os.path.join(HOME, "config.json")
LOG_PATH = os.path.join(HOME, "router.log")

DEFAULT_CONFIG = {
    "listen_host": "127.0.0.1",
    "listen_port": 4010,
    "router_token": "",
    "timeout_seconds": 90,
    "long_context_tokens": 120000,
    "providers": {
        "gemini": {"type": "openai", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "api_key": ""},
        "copilot": {"type": "anthropic", "base_url": "http://127.0.0.1:4141", "api_key": "copilot", "enabled": False, "autostart": True},
        "deepseek": {"type": "anthropic", "base_url": "https://api.deepseek.com/anthropic", "api_key": ""},
        "openrouter": {"type": "anthropic", "base_url": "https://openrouter.ai/api", "api_key": ""},
    },
    # tier -> ordered "provider:model" candidates. install.py fills real model ids.
    "tiers": {
        "background": ["gemini:gemini-flash-latest", "deepseek:deepseek-chat"],
        "simple": ["gemini:gemini-flash-latest", "deepseek:deepseek-chat"],
        "code": ["copilot:claude-sonnet-4.5", "gemini:gemini-pro-latest", "deepseek:deepseek-chat"],
        "hard": ["gemini:gemini-pro-latest", "copilot:claude-sonnet-4.5", "deepseek:deepseek-chat"],
        "long": ["gemini:gemini-pro-latest", "gemini:gemini-flash-latest"],
        "vision": ["gemini:gemini-pro-latest", "copilot:claude-sonnet-4.5"],
    },
}

_lock = threading.Lock()
_cfg_cache = {"mtime": 0, "cfg": None}
COOLDOWN = {}          # "provider:model" -> unix time until which it is skipped
SESSION_TIER = {}      # conversation key -> (tier, ts)
SIGS = {}              # tool_call id -> provider-specific extra_content (Gemini thought signatures)


def log(msg):
    line = "%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        os.makedirs(HOME, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def deep_merge(base, extra):
    out = dict(base)
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def get_config():
    try:
        mtime = os.path.getmtime(CONFIG_PATH)
    except OSError:
        mtime = 0
    with _lock:
        if _cfg_cache["cfg"] is None or mtime != _cfg_cache["mtime"]:
            user = {}
            if mtime:
                with open(CONFIG_PATH, encoding="utf-8") as f:
                    user = json.load(f)
            _cfg_cache["cfg"] = deep_merge(DEFAULT_CONFIG, user)
            _cfg_cache["mtime"] = mtime
        return _cfg_cache["cfg"]


def provider_enabled(cfg, name):
    p = cfg["providers"].get(name)
    if not p:
        return False
    if "enabled" in p:
        return bool(p["enabled"])
    key = p.get("api_key") or os.environ.get(name.upper() + "_API_KEY", "")
    return bool(key)


def provider_key(cfg, name):
    p = cfg["providers"][name]
    return p.get("api_key") or os.environ.get(name.upper() + "_API_KEY", "")


# ----------------------------------------------------------------- classify
HARD = re.compile(r"architect|design|\bplan\b|refactor|root cause|debug|investigat|security|migrat|optimi[sz]|"
                  r"ארכיטקטור|תכנ|ריפקטור|שכתוב|באג|חקור|אבטח|מיגרצ|אופטימיז", re.I)
SIMPLE = re.compile(r"explain|rename|typo|readme|comment|docstring|summari[sz]e|what does|"
                    r"הסבר|שנה שם|שגיאת כתיב|תעד|סכם|מה עושה", re.I)
FORCE = re.compile(r"^\s*!(background|simple|fast|code|hard|long|vision|gemini|copilot|deepseek|openrouter)\b", re.I)


def est_tokens(body):
    return len(json.dumps(body, ensure_ascii=False)) // 3


def block_text(content):
    if isinstance(content, str):
        return content
    out = []
    for b in content or []:
        if isinstance(b, dict) and b.get("type") == "text":
            out.append(b.get("text", ""))
    return "\n".join(out)


def has_image(messages):
    for m in messages[-4:]:
        c = m.get("content")
        if isinstance(c, list):
            for b in c:
                if isinstance(b, dict) and b.get("type") == "image":
                    return True
                if isinstance(b, dict) and b.get("type") == "tool_result" and isinstance(b.get("content"), list):
                    if any(isinstance(x, dict) and x.get("type") == "image" for x in b["content"]):
                        return True
    return False


def classify(body, cfg):
    """Return (tier, pinned_provider_or_None, reason)."""
    model = (body.get("model") or "").lower()
    msgs = body.get("messages") or []
    tokens = est_tokens(body)
    last = msgs[-1] if msgs else {}
    last_is_tool = (last.get("role") == "user" and isinstance(last.get("content"), list)
                    and last["content"] and all(isinstance(b, dict) and b.get("type") == "tool_result" for b in last["content"]))
    first_user = next((block_text(m.get("content")) for m in msgs if m.get("role") == "user"), "")
    key = hashlib.sha1(first_user[:400].encode("utf-8", "ignore")).hexdigest()
    last_text = ""
    for m in reversed(msgs):
        if m.get("role") == "user":
            t = block_text(m.get("content"))
            if t.strip():
                last_text = t
                break

    pin = None
    force = FORCE.match(last_text)
    forced_tier = None
    if force:
        w = force.group(1).lower()
        if w in ("gemini", "copilot", "deepseek", "openrouter"):
            pin = w
        else:
            forced_tier = {"fast": "simple"}.get(w, w)

    if "haiku" in model or (not body.get("tools") and (body.get("max_tokens") or 99999) <= 1024):
        return "background", pin, "background call"
    if has_image(msgs):
        return "vision", pin, "image in context"
    if tokens > cfg["long_context_tokens"]:
        return "long", pin, "~%d tokens" % tokens

    tier, why = None, ""
    sticky = SESSION_TIER.get(key)
    if forced_tier:
        tier, why = forced_tier, "forced by prompt"
    elif last_is_tool and sticky:
        tier, why = sticky[0], "continuing task"
    else:
        thinking = (body.get("thinking") or {}).get("type") in ("enabled", "adaptive")
        system_text = block_text(body.get("system"))
        if thinking or "plan mode is active" in system_text.lower():
            tier, why = "hard", "thinking/plan mode"
        elif HARD.search(last_text) and (len(last_text) > 200 or not SIMPLE.search(last_text)):
            tier, why = "hard", "keywords"
        elif SIMPLE.search(last_text) and len(last_text) < 400:
            tier, why = "simple", "keywords"
        else:
            tier, why = "code", "default"
    if tier not in cfg["tiers"]:
        tier = "code"
    if len(SESSION_TIER) > 500:
        SESSION_TIER.clear()
    SESSION_TIER[key] = (tier, time.time())
    return tier, pin, why


def candidates(cfg, tier, pin):
    now = time.time()
    raw = []
    for c in cfg["tiers"].get(tier, []):
        prov, _, model = c.partition(":")
        if pin and prov != pin:
            continue
        if provider_enabled(cfg, prov):
            raw.append((prov, model))
    ready = [c for c in raw if COOLDOWN.get("%s:%s" % c, 0) <= now]
    return ready or raw


# ------------------------------------------------------- anthropic -> openai
DROP_SCHEMA = {"$schema", "$id", "additionalProperties", "propertyNames", "patternProperties",
               "exclusiveMinimum", "exclusiveMaximum", "default", "examples"}


def clean_schema(node):
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k in DROP_SCHEMA:
                continue
            if k == "format" and v not in ("enum", "date-time"):
                continue
            out[k] = clean_schema(v)
        return out
    if isinstance(node, list):
        return [clean_schema(x) for x in node]
    return node


def flatten_result(content):
    if isinstance(content, str):
        return content
    parts = []
    for b in content or []:
        if isinstance(b, dict):
            parts.append(b.get("text", "[image]") if b.get("type") == "text" else "[%s]" % b.get("type", "content"))
    return "\n".join(parts)


def to_openai(body, model, stream):
    msgs = []
    system = body.get("system")
    if system:
        msgs.append({"role": "system", "content": system if isinstance(system, str) else block_text(system)})
    names = {}
    for m in body.get("messages", []):
        c = m.get("content")
        if isinstance(c, list):
            for b in c:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    names[b["id"]] = b["name"]
    for m in body.get("messages", []):
        c = m.get("content")
        if isinstance(c, str):
            msgs.append({"role": m["role"], "content": c})
            continue
        if m["role"] == "user":
            parts, tool_msgs = [], []
            for b in c:
                t = b.get("type")
                if t == "text":
                    parts.append({"type": "text", "text": b.get("text", "")})
                elif t == "image":
                    s = b.get("source", {})
                    url = ("data:%s;base64,%s" % (s.get("media_type", "image/png"), s.get("data", ""))
                           if s.get("type") == "base64" else s.get("url", ""))
                    parts.append({"type": "image_url", "image_url": {"url": url}})
                elif t == "tool_result":
                    txt = flatten_result(b.get("content"))
                    if b.get("is_error"):
                        txt = "Error: " + txt
                    tm = {"role": "tool", "tool_call_id": b["tool_use_id"], "content": txt}
                    if b["tool_use_id"] in names:
                        tm["name"] = names[b["tool_use_id"]]
                    tool_msgs.append(tm)
            msgs.extend(tool_msgs)
            if parts:
                if all(p["type"] == "text" for p in parts):
                    msgs.append({"role": "user", "content": "\n".join(p["text"] for p in parts)})
                else:
                    msgs.append({"role": "user", "content": parts})
        else:
            text, calls = [], []
            for b in c:
                if b.get("type") == "text":
                    text.append(b.get("text", ""))
                elif b.get("type") == "tool_use":
                    call = {"id": b["id"], "type": "function",
                            "function": {"name": b["name"], "arguments": json.dumps(b.get("input", {}), ensure_ascii=False)}}
                    if b["id"] in SIGS:
                        call["extra_content"] = SIGS[b["id"]]
                    calls.append(call)
            if not text and not calls:
                continue
            am = {"role": "assistant", "content": "".join(text) or None}
            if calls:
                am["tool_calls"] = calls
            msgs.append(am)
    out = {"model": model, "messages": msgs, "stream": stream}
    if stream:
        out["stream_options"] = {"include_usage": True}
    if body.get("max_tokens"):
        out["max_tokens"] = body["max_tokens"]
    if body.get("temperature") is not None:
        out["temperature"] = body["temperature"]
    if body.get("stop_sequences"):
        out["stop"] = body["stop_sequences"]
    if body.get("tools"):
        out["tools"] = [{"type": "function", "function": {
            "name": t["name"], "description": t.get("description", ""),
            "parameters": clean_schema(t.get("input_schema") or {"type": "object", "properties": {}})}}
            for t in body["tools"]]
        tc = body.get("tool_choice") or {}
        if tc.get("type") == "any":
            out["tool_choice"] = "required"
        elif tc.get("type") == "tool":
            out["tool_choice"] = {"type": "function", "function": {"name": tc.get("name")}}
        elif tc.get("type") == "none":
            out["tool_choice"] = "none"
    return out


def stop_reason(finish, has_tools):
    if has_tools or finish == "tool_calls":
        return "tool_use"
    return "max_tokens" if finish == "length" else "end_turn"


def openai_to_message(resp, model):
    ch = (resp.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    content = []
    if msg.get("content"):
        content.append({"type": "text", "text": msg["content"]})
    for tc in msg.get("tool_calls") or []:
        try:
            args = json.loads(tc["function"].get("arguments") or "{}")
        except ValueError:
            args = {}
        tid = tc.get("id") or "toolu_" + uuid.uuid4().hex[:20]
        if tc.get("extra_content"):
            SIGS[tid] = tc["extra_content"]
        content.append({"type": "tool_use", "id": tid, "name": tc["function"]["name"], "input": args})
    if not content:
        content.append({"type": "text", "text": ""})
    u = resp.get("usage") or {}
    return {"id": "msg_" + uuid.uuid4().hex[:24], "type": "message", "role": "assistant", "model": model,
            "content": content, "stop_reason": stop_reason(ch.get("finish_reason"), bool(msg.get("tool_calls"))),
            "stop_sequence": None,
            "usage": {"input_tokens": u.get("prompt_tokens", 0), "output_tokens": u.get("completion_tokens", 0)}}


def sse(event, data):
    return ("event: %s\ndata: %s\n\n" % (event, json.dumps(data, ensure_ascii=False))).encode("utf-8")


def stream_openai_to_anthropic(resp, write, model):
    write(sse("message_start", {"type": "message_start", "message": {
        "id": "msg_" + uuid.uuid4().hex[:24], "type": "message", "role": "assistant", "model": model,
        "content": [], "stop_reason": None, "stop_sequence": None,
        "usage": {"input_tokens": 0, "output_tokens": 0}}}))
    st = {"next": 0, "open": None, "tools": {}, "any_tool": False, "wrote": False}
    finish, usage = None, {}

    def close_open():
        if st["open"] is not None:
            write(sse("content_block_stop", {"type": "content_block_stop", "index": st["open"]}))
            st["open"] = None

    def open_block(block):
        close_open()
        idx = st["next"]
        st["next"] += 1
        st["open"] = idx
        st["wrote"] = True
        write(sse("content_block_start", {"type": "content_block_start", "index": idx, "content_block": block}))
        return idx

    text_idx = None
    for raw in resp:
        line = raw.decode("utf-8", "ignore").strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            break
        try:
            chunk = json.loads(payload)
        except ValueError:
            continue
        if chunk.get("usage"):
            usage = chunk["usage"]
        for ch in chunk.get("choices") or []:
            d = ch.get("delta") or {}
            if d.get("content"):
                if text_idx is None or st["open"] != text_idx:
                    text_idx = open_block({"type": "text", "text": ""})
                write(sse("content_block_delta", {"type": "content_block_delta", "index": text_idx,
                                                  "delta": {"type": "text_delta", "text": d["content"]}}))
            for tc in d.get("tool_calls") or []:
                i = tc.get("index", 0)
                cur = st["tools"].get(i)
                if cur is None or (tc.get("id") and tc["id"] != cur["id"]):
                    tid = tc.get("id") or "toolu_" + uuid.uuid4().hex[:20]
                    idx = open_block({"type": "tool_use", "id": tid,
                                      "name": (tc.get("function") or {}).get("name", ""), "input": {}})
                    cur = {"id": tid, "block": idx}
                    st["tools"][i] = cur
                    st["any_tool"] = True
                if tc.get("extra_content"):
                    SIGS[cur["id"]] = tc["extra_content"]
                args = (tc.get("function") or {}).get("arguments")
                if args and st["open"] == cur["block"]:
                    write(sse("content_block_delta", {"type": "content_block_delta", "index": cur["block"],
                                                      "delta": {"type": "input_json_delta", "partial_json": args}}))
            if ch.get("finish_reason"):
                finish = ch["finish_reason"]
    if not st["wrote"]:
        open_block({"type": "text", "text": ""})
    close_open()
    write(sse("message_delta", {"type": "message_delta",
                                "delta": {"stop_reason": stop_reason(finish, st["any_tool"]), "stop_sequence": None},
                                "usage": {"input_tokens": usage.get("prompt_tokens", 0),
                                          "output_tokens": usage.get("completion_tokens", 0)}}))
    write(sse("message_stop", {"type": "message_stop"}))


# ------------------------------------------------------------------ server
class UpstreamError(Exception):
    def __init__(self, status, detail):
        Exception.__init__(self, "%s %s" % (status, detail))
        self.status = status
        self.detail = detail


def http_open(url, payload, headers, timeout):
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        raise UpstreamError(e.code, e.read()[:400].decode("utf-8", "ignore"))
    except (urllib.error.URLError, OSError) as e:
        raise UpstreamError(0, str(e))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"      # body ends when the connection closes: no chunking needed

    def log_message(self, *a):
        pass

    def _json(self, status, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authed(self, cfg):
        tok = cfg.get("router_token")
        if not tok:
            return True
        got = (self.headers.get("x-api-key") or self.headers.get("Authorization", "").replace("Bearer ", "")).strip()
        return got == tok

    def do_GET(self):
        cfg = get_config()
        if self.path.startswith("/health"):
            return self._json(200, {"ok": True})
        if not self._authed(cfg):
            return self._json(401, {"type": "error", "error": {"type": "authentication_error", "message": "bad token"}})
        if self.path.startswith("/status"):
            return self._json(200, {"providers": [p for p in cfg["providers"] if provider_enabled(cfg, p)],
                                    "cooldown": {k: int(v - time.time()) for k, v in COOLDOWN.items() if v > time.time()}})
        self._json(404, {"error": "not found"})

    def do_POST(self):
        cfg = get_config()
        if not self._authed(cfg):
            return self._json(401, {"type": "error", "error": {"type": "authentication_error", "message": "bad token"}})
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            return self._json(400, {"type": "error", "error": {"type": "invalid_request_error", "message": "bad json"}})
        path = self.path.split("?")[0]
        if path.endswith("/count_tokens"):
            return self._json(200, {"input_tokens": est_tokens(body)})
        if path.endswith("/v1/messages"):
            return self.handle_messages(body, cfg)
        self._json(404, {"error": "not found"})

    def handle_messages(self, body, cfg):
        tier, pin, why = classify(body, cfg)
        stream = bool(body.get("stream"))
        cands = candidates(cfg, tier, pin)
        last = None
        for prov, model in cands:
            t0 = time.time()
            try:
                if cfg["providers"][prov]["type"] == "anthropic":
                    self.forward_anthropic(cfg, prov, model, body, stream)
                else:
                    self.forward_openai(cfg, prov, model, body, stream)
                log("tier=%s (%s) -> %s:%s ok %.1fs ~%dtok" % (tier, why, prov, model, time.time() - t0, est_tokens(body)))
                return
            except UpstreamError as e:
                COOLDOWN["%s:%s" % (prov, model)] = time.time() + (600 if e.status in (401, 403, 404) else 60)
                log("tier=%s -> %s:%s FAILED %s" % (tier, prov, model, str(e)[:300]))
                last = e
            except (BrokenPipeError, ConnectionResetError):
                return
        msg = "no provider available for tier '%s'" % tier if last is None else "all providers failed: %s" % last
        self._json(529 if last else 503, {"type": "error", "error": {"type": "overloaded_error", "message": msg}})

    def forward_anthropic(self, cfg, prov, model, body, stream):
        p = cfg["providers"][prov]
        key = provider_key(cfg, prov)
        b = dict(body)
        b["model"] = model
        b.pop("context_management", None)
        headers = {"content-type": "application/json", "anthropic-version": "2023-06-01",
                   "authorization": "Bearer " + key, "x-api-key": key}
        resp = http_open(p["base_url"].rstrip("/") + "/v1/messages", json.dumps(b).encode("utf-8"), headers,
                         cfg["timeout_seconds"])
        self.send_response(200)
        self.send_header("Content-Type", resp.headers.get("Content-Type", "application/json"))
        self.end_headers()
        try:
            while True:
                chunk = resp.read1(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (OSError, ValueError) as e:
            if not isinstance(e, (BrokenPipeError, ConnectionResetError)):
                log("stream cut %s:%s %s" % (prov, model, e))
            raise

    def forward_openai(self, cfg, prov, model, body, stream):
        p = cfg["providers"][prov]
        key = provider_key(cfg, prov)
        payload = json.dumps(to_openai(body, model, stream), ensure_ascii=False).encode("utf-8")
        headers = {"content-type": "application/json", "authorization": "Bearer " + key}
        resp = http_open(p["base_url"].rstrip("/") + "/chat/completions", payload, headers, cfg["timeout_seconds"])
        if not stream:
            data = openai_to_message(json.loads(resp.read().decode("utf-8")), model)
            return self._json(200, data)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        def write(b):
            self.wfile.write(b)
            self.wfile.flush()
        try:
            stream_openai_to_anthropic(resp, write, model)
        except (BrokenPipeError, ConnectionResetError):
            raise
        except Exception as e:   # headers already sent: report in-band
            log("stream error %s:%s %s" % (prov, model, e))
            try:
                write(sse("error", {"type": "error", "error": {"type": "api_error", "message": str(e)}}))
            except OSError:
                pass


def port_open(host, port):
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def ensure_copilot(cfg):
    p = cfg["providers"].get("copilot")
    if not p or not p.get("enabled") or not p.get("autostart"):
        return
    m = re.search(r":(\d+)$", p["base_url"].rstrip("/"))
    port = int(m.group(1)) if m else 4141
    if port_open("127.0.0.1", port):
        return
    npx = "npx.cmd" if os.name == "nt" else "npx"
    try:
        logf = open(os.path.join(HOME, "copilot-api.log"), "ab")
        kw = {"creationflags": 0x00000008 | 0x00000200} if os.name == "nt" else {"start_new_session": True}
        subprocess.Popen([npx, "--yes", "copilot-api@latest", "start", "--port", str(port),
                          "--account-type", p.get("account_type", "individual")],
                         stdout=logf, stderr=logf, stdin=subprocess.DEVNULL, **kw)
        log("started copilot-api on port %d" % port)
    except OSError as e:
        log("could not start copilot-api: %s" % e)


def serve():
    cfg = get_config()
    ensure_copilot(cfg)
    srv = ThreadingHTTPServer((cfg["listen_host"], cfg["listen_port"]), Handler)
    srv.daemon_threads = True
    log("router listening on %s:%d" % (cfg["listen_host"], cfg["listen_port"]))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


def list_models(cfg, name):
    """Return model ids a provider offers (best effort)."""
    p = cfg["providers"][name]
    key = provider_key(cfg, name)
    base = p["base_url"].rstrip("/")
    url = base + ("/models" if p["type"] == "openai" else "/v1/models")
    req = urllib.request.Request(url, headers={"authorization": "Bearer " + key, "x-api-key": key,
                                               "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    items = data.get("data") or data.get("models") or []
    return [(i.get("id") or i.get("name", "")).replace("models/", "") for i in items]


def selftest():
    cfg = get_config()
    ok_all = True
    for name in cfg["providers"]:
        if not provider_enabled(cfg, name):
            print("-  %-10s disabled (no key)" % name)
            continue
        models = [c.partition(":")[2] for t in cfg["tiers"].values() for c in t if c.startswith(name + ":")]
        model = models[0] if models else ""
        body = {"model": model, "max_tokens": 32, "messages": [{"role": "user", "content": "Reply with the single word: ok"}]}
        try:
            if cfg["providers"][name]["type"] == "anthropic":
                h = {"content-type": "application/json", "anthropic-version": "2023-06-01",
                     "authorization": "Bearer " + provider_key(cfg, name), "x-api-key": provider_key(cfg, name)}
                r = http_open(cfg["providers"][name]["base_url"].rstrip("/") + "/v1/messages",
                              json.dumps(body).encode(), h, 60)
                txt = block_text(json.loads(r.read().decode())["content"])
            else:
                h = {"content-type": "application/json", "authorization": "Bearer " + provider_key(cfg, name)}
                r = http_open(cfg["providers"][name]["base_url"].rstrip("/") + "/chat/completions",
                              json.dumps(to_openai(body, model, False)).encode(), h, 60)
                txt = block_text(openai_to_message(json.loads(r.read().decode()), model)["content"])
            print("OK %-10s %-28s -> %r" % (name, model, txt.strip()[:40]))
        except Exception as e:
            ok_all = False
            print("XX %-10s %-28s %s" % (name, model, str(e)[:200]))
    return 0 if ok_all else 1


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if cmd == "serve":
        serve()
    elif cmd == "models":
        c = get_config()
        for n in c["providers"]:
            if provider_enabled(c, n):
                try:
                    print("%s: %s" % (n, ", ".join(sorted(list_models(c, n)))))
                except Exception as e:
                    print("%s: error %s" % (n, e))
    elif cmd == "selftest":
        sys.exit(selftest())
    else:
        print(__doc__)
