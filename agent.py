#!/usr/bin/env python3
"""
Mini Agent - runs in GitHub Actions, no server needed.

Talks to Roar AI (DeepSeek Flash v4) and posts the answer to Telegram.
Runs on a schedule, on a button press, or ad-hoc with --message.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROAR_BASE = "https://api.roar-ai.com/v1"
MODEL = os.environ.get("MINI_MODEL", "deepseek-v4.1-flash")
# DeepSeek spends reasoning tokens before emitting visible text.
# Below ~400 the answer gets truncated or corrupted. Never lower this.
MAX_TOKENS = int(os.environ.get("MINI_MAX_TOKENS", "800"))
TG_LIMIT = 4000  # Telegram hard cap is 4096; leave headroom

ROOT = Path(__file__).resolve().parent


def log(msg):
    print(msg, flush=True)


def post_json(url, payload, headers, timeout=180, attempts=3):
    body = json.dumps(payload).encode()
    last = None
    for i in range(attempts):
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:400]
            last = "HTTP %s: %s" % (e.code, detail)
            if e.code in (429, 500, 502, 503, 504) and i < attempts - 1:
                time.sleep(2 ** (i + 1))
                continue
            raise RuntimeError(last)
        except Exception as e:
            last = str(e)
            if i < attempts - 1:
                time.sleep(2 ** (i + 1))
                continue
            raise RuntimeError(last)
    raise RuntimeError(last or "unknown error")


def ask_roar(prompt, system=None):
    key = os.environ.get("ROAR_AI_API_KEY")
    if not key:
        raise SystemExit("ROAR_AI_API_KEY is not set")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    data = post_json(
        ROAR_BASE + "/chat/completions",
        {"model": MODEL, "messages": messages, "max_tokens": MAX_TOKENS, "temperature": 0.7},
        {"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    choice = (data.get("choices") or [{}])[0]
    text = ((choice.get("message") or {}).get("content") or "").strip()
    usage = data.get("usage") or {}
    if not text:
        raise RuntimeError("model returned empty content (raise MAX_TOKENS)")
    log("tokens in=%s out=%s finish=%s" % (
        usage.get("prompt_tokens"), usage.get("completion_tokens"), choice.get("finish_reason")))
    return text


def send_telegram(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        log("!! TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing - printing instead\n")
        log(text)
        return False
    if os.environ.get("DRY_RUN") == "1":
        log("DRY_RUN: would send %d chars\n%s" % (len(text), text))
        return True
    url = "https://api.telegram.org/bot%s/sendMessage" % token
    chunks, cur = [], ""
    for line in text.splitlines(keepends=True):
        while len(line) > TG_LIMIT:
            chunks.append(line[:TG_LIMIT])
            line = line[TG_LIMIT:]
        if len(cur) + len(line) > TG_LIMIT:
            chunks.append(cur)
            cur = ""
        cur += line
    if cur.strip():
        chunks.append(cur)
    if not chunks:
        chunks = ["(empty)"]
    for i, c in enumerate(chunks):
        if len(chunks) > 1:
            c = c + "\n\n(%d/%d)" % (i + 1, len(chunks))
        post_json(url, {"chat_id": chat, "text": c, "disable_web_page_preview": True},
                  {"Content-Type": "application/json"})
        log("sent chunk %d/%d" % (i + 1, len(chunks)))
    return True


def load_tasks():
    path = ROOT / "tasks.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {t["name"]: t for t in data.get("tasks", [])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", help="name of a task in tasks.json")
    ap.add_argument("--message", help="ad-hoc prompt instead of a task")
    ap.add_argument("--list", action="store_true", help="list available tasks")
    args = ap.parse_args()

    tasks = load_tasks()

    if args.list:
        for n, t in tasks.items():
            log("- %-16s [%s]  %s" % (n, "on" if t.get("enabled", True) else "off", t.get("title", "")))
        return 0

    if args.message:
        prompt, title = args.message, None
    else:
        name = args.task or os.environ.get("MINI_TASK") or "morning"
        task = tasks.get(name)
        if not task:
            log("task %r not found. available: %s" % (name, ", ".join(tasks) or "none"))
            return 2
        if not task.get("enabled", True):
            log("task %r is disabled - nothing to do" % name)
            return 0
        prompt, title = task["prompt"], task.get("title") or name

    log("model=%s task=%s" % (MODEL, title or "adhoc"))
    try:
        answer = ask_roar(prompt)
    except Exception as e:
        send_telegram("mini-agent failed: %s" % e)
        raise
    send_telegram(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
