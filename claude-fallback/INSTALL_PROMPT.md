# משימה: התקנה ואימות של "claude-fallback" על המחשב הזה

אתה Claude Code שרץ על המחשב של המשתמש (לא בענן). המשתמש מדבר עברית: כל ההסברים והדוחות אליו בעברית, קוד והודעות commit באנגלית.

## המטרה
כשהמכסה של Claude Code נגמרת באמצע עבודה, לא לחכות. נפתח **אוטומטית** חלון טרמינל חדש באותה תיקייה שממשיך את **אותה שיחה** (`claude --continue`) דרך ראוטר מקומי קטן. הראוטר מדבר בפורמט Anthropic Messages מול Claude Code, **בוחר לכל בקשה את המודל המתאים לסוג המשימה** (רקע / פשוט / קוד / קשה / הקשר ארוך / תמונות), ועובר לספק הבא אם ספק נכשל. הספקים: **Gemini** (חשבון של המשתמש), **GitHub Copilot** (למשתמש יש מנוי), ובאופציה DeepSeek ו-OpenRouter.

הרקע: מאמר ב-theailazyleader.com על הריפו `nicedreamzapp/claude-code-local` (פקודת `keep going` שממשיכה שיחה על מודל אחר). הפתרון שלו פותח חלון אוטומטי רק במק או דרך Moonstone, והוא לא בוחר מודל לפי משימה ולא מחבר Gemini/Copilot. לכן נכתב פתרון משלנו, בנוי כך: hook מסוג `StopFailure` (matcher: `rate_limit`) ← `handoff.py` ← פותח טרמינל ← `claude --continue` עם `ANTHROPIC_BASE_URL` שמצביע על הראוטר.

## למה אתה כאן (חשוב)
הקוד למטה נכתב בסביבת ענן **בלי גישה לספקים אמיתיים ובלי Claude Code אמיתי**. הוא נבדק רק מול שרתי דמה. **אל תסמוך עליו.** התפקיד שלך: לבדוק, לתקן ורק אז להתקין. הנחות שלא אומתו וחובה לאמת מול התיעוד הרשמי ומול המחשב עצמו:

1. ל-Claude Code יש hook בשם `StopFailure` עם matcher `rate_limit`, והוא מקבל JSON ב-stdin עם השדה `cwd`. (בדוק בתיעוד הרשמי של hooks ובגרסה המותקנת: `claude --version`.)
2. `claude --continue "prompt"` ממשיך את השיחה האחרונה בתיקייה גם כשמוגדרים `ANTHROPIC_BASE_URL` ו-`ANTHROPIC_AUTH_TOKEN`, ולא מבקש התחברות מחדש. אם צריך `ANTHROPIC_API_KEY` במקום, או `--resume`, תקן.
3. נקודות קצה תואמות Anthropic: DeepSeek (`https://api.deepseek.com/anthropic`), OpenRouter (`https://openrouter.ai/api`), ו-`copilot-api` (פורט 4141, `/v1/messages`). אמת כתובות, כותרות אימות והדגלים (`start --port --account-type`, `auth`).
4. Gemini דרך נקודת הקצה התואמת ל-OpenAI (`https://generativelanguage.googleapis.com/v1beta/openai`): הסכמות של כלים, הסטרימינג, והחזרת `thought_signature` ב-`extra_content` בקריאות כלים (בלי זה Gemini 3 עלול להחזיר 400).
5. בחירת שמות המודלים ב-`install.py` (`pick_models`) היא היוריסטיקה. בדוק מול הרשימות האמיתיות ותקן.
6. תאימות פלטפורמה: איך נפתח טרמינל חדש (macOS / Windows / Linux / WSL) במחשב הזה.

## כללי בטיחות (מחייבים)
- **אל תבקש מהמשתמש להדביק מפתחות API או טוקנים בצ'אט, ואל תקרא או תדפיס אותם.** השלבים האינטראקטיביים (הזנת מפתחות, התחברות device login ל-GitHub) המשתמש מריץ בעצמו בטרמינל. תן לו את הפקודה המדויקת (אפשר עם הקידומת `!` בסשן הזה). אחרי זה אתה בודק רק אם הצליח.
- לפני שינוי של `~/.claude/settings.json`: גיבוי, הצגת ה-diff, ואישור המשתמש. אל תמחק hooks קיימים.
- אל תערוך קבצי shell (`.bashrc`, `.zshrc`, PATH) בלי לשאול.
- הכל מותקן ב-`~/.claude-fallback` ולא בתוך שום ריפו. אל תבצע commit או push של קבצים או מפתחות.
- בקבצים ה-`config.json` נשמר עם הרשאות 600. אל תכניס מפתחות ללוגים.
- פרטיות: בזמן גיבוי, קוד הפרויקט נשלח לספקים שהופעלו. הזכר זאת למשתמש, ושאל אם יש פרויקטים רגישים שצריך להחריג.
- Copilot עובד דרך `copilot-api`, פרויקט לא רשמי שמבוסס על הנדסה לאחור. GitHub מזהירה ששימוש אוטומטי אינטנסיבי עלול להפעיל זיהוי ניצול. הצג זאת למשתמש לפני ההפעלה וקבל הסכמה מפורשת.

## שלבי העבודה (בצע לפי הסדר, ודווח בקצרה אחרי כל שלב)

### שלב 0: סקירת המחשב (קריאה בלבד)
אסוף ודווח: מערכת הפעלה וגרסה, shell, האם זה WSL, `python3 --version` (נדרש 3.8+), `node --version` ו-`npx` (נדרש 20+ ל-Copilot), `claude --version`, האם `claude` ב-PATH, תוכן קיים של `~/.claude/settings.json` (במיוחד `hooks`; אל תציג מפתחות), האם פורטים 4010 ו-4141 פנויים, איזה אמולטור טרמינל קיים/זמין, האם קיים כבר `~/.claude-fallback`, והאם משתני סביבה `ANTHROPIC_*` מוגדרים. אל תמשיך אם חסר Python או Claude Code, ושאל איך להמשיך.

### שלב 1: אימות הנחות מול התיעוד
עבור על ששת הסעיפים שלמעלה. השתמש בתיעוד הרשמי (code.claude.com/docs, README של `copilot-api`, תיעוד DeepSeek ו-OpenRouter ו-Gemini) ובבדיקות מקומיות. אל תנחש: אם אי אפשר לאמת משהו, סמן אותו כ"לא אומת" בדוח.

### שלב 2: סקירת קוד ותיקון
קרא את ארבעת הקבצים למטה בעין ביקורתית: נכונות, אבטחה (למשל האזנה רק ל-127.0.0.1, אימות בטוקן), טיפול בשגיאות, תאימות לפלטפורמה של המחשב הזה. תקן מה שצריך. כתוב אותם ל-`~/.claude-fallback/src/` (או לתיקייה זמנית), הרץ `python3 test_router.py` (חייב לעבור: `ALL TESTS PASSED`), ואם שינית התנהגות, הוסף בדיקה.

### שלב 3: התקנה
1. הצג למשתמש תכנית קצרה של מה יותקן ומה ישתנה, וקבל אישור.
2. `install.py` הוא אינטראקטיבי ומבקש מפתחות. אל תריץ אותו בעצמך עם מפתחות. תן למשתמש להריץ בטרמינל: `python3 <נתיב>/install.py`. (אם ביקשת ממנו, הוא יכול להריץ אותו מהסשן עם `!`.)
3. אחרי שסיים: אמת שנוצרו `~/.claude-fallback/config.json` (הרשאות 600), `router.py`, `handoff.py`, ושה-hook נוסף ל-`settings.json` בלי לפגוע בקיים.

### שלב 4: אימות אמיתי
1. `python3 ~/.claude-fallback/router.py selftest`: כל ספק מופעל חייב לענות. אם ספק נכשל, אבחן (שם מודל, מפתח, פורט, כותרות) ותקן.
2. בדיקת ניתוב אמיתית: הפעל את הראוטר, ואז `ANTHROPIC_BASE_URL=http://127.0.0.1:4010 ANTHROPIC_AUTH_TOKEN=<router_token מה-config, בלי להדפיס אותו> claude -p "say ok"` והראה ב-`~/.claude-fallback/router.log` לאיזה ספק ומודל הבקשה הגיעה. נסה גם בקשה שמשתמשת בכלי (קריאת קובץ) כדי לוודא שהמרת הכלים ל-Gemini עובדת, וגם בקשת "תכנון" כדי לוודא ניתוב לשכבה `hard`.
3. בדיקת המעבר: הרץ את `handoff.py` עם payload מדומה (`echo '{"cwd":"<תיקייה>"}' | python3 ~/.claude-fallback/handoff.py`) ואמת שנפתח טרמינל חדש שמריץ `claude --continue` דרך הראוטר. אם לא נפתח, תקן את `open_terminal` לפי הטרמינל במחשב הזה.
4. אם אפשר לוודא שה-hook `StopFailure` באמת נטען (למשל דרך `/hooks` בתוך Claude Code), הראה זאת. אי אפשר לגרום למכסה להיגמר בכוונה, אז אמור במפורש שהקצה הזה נבדק רק בהדמיה.

### שלב 5: דוח סופי בעברית
טבלה קצרה: מה הותקן ואיפה; מה אומת בפועל; מה לא אומת; מה שונה בקוד לעומת המקור; איך משתמשים (`keepgoing`, כיבוי עם `CLAUDE_FALLBACK_AUTO=0`, עריכת `tiers` ב-`config.json`, כפיית מודל עם `!hard` / `!fast` / `!gemini` / `!copilot` בתחילת הודעה); איך מסירים (`~/.claude-fallback`, הסרת ה-hook מ-`settings.json`, גיבוי ב-`settings.json.bak-claude-fallback`); ואזהרות הפרטיות וה-Copilot.

## הקבצים
כל קובץ נשמר בשם שבכותרת שלו, באותה תיקייה.

### FILE: router.py

````python
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
````

### FILE: handoff.py

````python
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
````

### FILE: install.py

````python
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
````

### FILE: test_router.py

````python
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
````

## התחל עכשיו משלב 0.
