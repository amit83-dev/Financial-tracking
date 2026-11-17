"""Offline tests: fake Gemini (OpenAI-style) and fake Anthropic upstreams, real router."""
import json, os, sys, tempfile, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOME = tempfile.mkdtemp()
os.environ["CLAUDE_FALLBACK_HOME"] = HOME
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import router  # noqa

SEEN = {"oa": [], "an": []}


class FakeOA(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        b = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN["oa"].append(b)
        if b["stream"]:
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            ch = [{"choices": [{"delta": {"content": "Hel"}}]}, {"choices": [{"delta": {"content": "lo"}}]},
                  {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "Read", "arguments": "{\"pa"},
                                                          "extra_content": {"google": {"thought_signature": "SIG"}}}]}}]},
                  {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "th\":\"a\"}"}}]}}]},
                  {"choices": [{"delta": {"tool_calls": [{"index": 1, "id": "c2", "function": {"name": "Bash", "arguments": "{}"}}]}}]},
                  {"choices": [{"delta": {}, "finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 7, "completion_tokens": 3}}]
            for c in ch:
                self.wfile.write(("data: %s\n\n" % json.dumps(c)).encode()); self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
        else:
            d = json.dumps({"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                            "usage": {"prompt_tokens": 1, "completion_tokens": 1}}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(d))); self.end_headers(); self.wfile.write(d)


class FakeAN(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        b = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN["an"].append(b)
        if b["model"] == "broken":
            self.send_response(500); self.end_headers(); self.wfile.write(b"boom"); return
        d = json.dumps({"id": "x", "type": "message", "role": "assistant", "model": b["model"],
                        "content": [{"type": "text", "text": "an-ok"}], "stop_reason": "end_turn",
                        "usage": {"input_tokens": 1, "output_tokens": 1}}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(d)


def start(h):
    s = ThreadingHTTPServer(("127.0.0.1", 0), h); threading.Thread(target=s.serve_forever, daemon=True).start()
    return s.server_address[1]


oa, an = start(FakeOA), start(FakeAN)
cfg = {"listen_port": 0, "router_token": "tok",
       "providers": {"gemini": {"base_url": "http://127.0.0.1:%d" % oa, "api_key": "g"},
                     "copilot": {"base_url": "http://127.0.0.1:%d" % an, "enabled": True, "autostart": False},
                     "deepseek": {"base_url": "http://127.0.0.1:%d" % an, "api_key": ""}, "openrouter": {"api_key": ""}},
       "tiers": {"background": ["gemini:flash"], "simple": ["gemini:flash"],
                 "code": ["copilot:broken", "copilot:sonnet", "gemini:pro"], "hard": ["gemini:pro"],
                 "long": ["gemini:pro"], "vision": ["gemini:pro"]}}
json.dump(cfg, open(router.CONFIG_PATH, "w"))
srv = ThreadingHTTPServer(("127.0.0.1", 0), router.Handler); threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:%d/v1/messages" % srv.server_address[1]


def post(body, tok="tok"):
    req = urllib.request.Request(URL, json.dumps(body).encode(), {"content-type": "application/json", "x-api-key": tok})
    return urllib.request.urlopen(req, timeout=10)


def run():
    # auth
    try:
        post({"model": "x", "messages": []}, "bad"); assert False
    except urllib.error.HTTPError as e:
        assert e.code == 401
    base = {"model": "claude-sonnet", "max_tokens": 4096, "tools": [{"name": "Read", "input_schema": {"type": "object", "additionalProperties": False, "properties": {"path": {"type": "string", "format": "uri"}}}}]}
    # code tier: first candidate 500 -> failover to copilot:sonnet (anthropic passthrough)
    r = json.loads(post(dict(base, messages=[{"role": "user", "content": "add a field to the form"}])).read())
    assert r["content"][0]["text"] == "an-ok" and SEEN["an"][-1]["model"] == "sonnet", r
    # hard tier via keyword -> gemini non-stream conversion
    r = json.loads(post(dict(base, messages=[{"role": "user", "content": "plan the architecture of the sync layer"}])).read())
    assert r["content"][0]["text"] == "ok" and SEEN["oa"][-1]["model"] == "pro"
    t = SEEN["oa"][-1]["tools"][0]["function"]["parameters"]
    assert "additionalProperties" not in t and "format" not in t["properties"]["path"]
    # background (haiku) -> flash, tier "simple/background" list
    post(dict(base, model="claude-haiku", messages=[{"role": "user", "content": "title?"}]))
    assert SEEN["oa"][-1]["model"] == "flash"
    # streaming translation incl. tool calls + signature round-trip
    body = dict(base, stream=True, messages=[{"role": "user", "content": "debug the crash in sync"}])
    ev = post(body).read().decode()
    kinds = [l[7:] for l in ev.splitlines() if l.startswith("event: ")]
    assert kinds[0] == "message_start" and kinds[-1] == "message_stop", kinds
    assert kinds.count("content_block_start") == 3 and kinds.count("content_block_stop") == 3, kinds
    data = [json.loads(l[6:]) for l in ev.splitlines() if l.startswith("data: ")]
    args = "".join(d["delta"]["partial_json"] for d in data if d["type"] == "content_block_delta" and d["delta"]["type"] == "input_json_delta")
    assert args == '{"path":"a"}{}', args
    assert [d for d in data if d["type"] == "message_delta"][0]["delta"]["stop_reason"] == "tool_use"
    assert router.SIGS["c1"]["google"]["thought_signature"] == "SIG"
    # continuation with tool_result stays on the sticky tier (hard->gemini) and sends signature back
    msgs = body["messages"] + [{"role": "assistant", "content": [{"type": "tool_use", "id": "c1", "name": "Read", "input": {"path": "a"}}]},
                               {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "file text"}]}]
    post(dict(base, messages=msgs))
    last = SEEN["oa"][-1]
    assert last["model"] == "pro" and last["messages"][-1] == {"role": "tool", "tool_call_id": "c1", "content": "file text", "name": "Read"}
    assert last["messages"][-2]["tool_calls"][0]["extra_content"]["google"]["thought_signature"] == "SIG"
    # forced provider + image -> vision
    post(dict(base, messages=[{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "AA"}}, {"type": "text", "text": "what is this"}]}]))
    assert SEEN["oa"][-1]["messages"][-1]["content"][0]["type"] == "image_url"
    # count_tokens
    req = urllib.request.Request(URL + "/count_tokens", json.dumps({"messages": [{"role": "user", "content": "hi"}]}).encode(), {"x-api-key": "tok"})
    assert json.loads(urllib.request.urlopen(req).read())["input_tokens"] > 0
    print("ALL TESTS PASSED")


run()
