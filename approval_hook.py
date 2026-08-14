#!/usr/bin/env python3
"""PreToolUse hook: the summoned agent's permission gate.

Read-only tools pass instantly. Anything else posts an approval request into
the Feishu thread that summoned the agent, and waits for the OWNER (and only
the owner) to reply 允许 / 拒绝. Timeout means deny.

Claude Code invokes this with the tool call as JSON on stdin; we answer with
a permissionDecision on stdout. Context arrives via TTMA_* environment
variables set by bridge.py.
"""

import atexit
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

GRANTS_DIR = Path(os.environ.get("TTMA_HOME", Path.home() / ".talk-to-my-agent")) / "grants"
ASK_LOCK = GRANTS_DIR.parent / "approval.lock"


def acquire_ask_lock(max_wait, session_id):
    """One outstanding 🔐 at a time: parallel tool calls otherwise flood the chat
    and a single 允许 gets consumed by every waiting poller at once. Returns
    'granted' if a blanket grant appears while waiting (skip asking entirely)."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        if session_id and (GRANTS_DIR / session_id).exists():
            return "granted"
        try:
            os.mkdir(ASK_LOCK)
            return "locked"
        except FileExistsError:
            try:
                if time.time() - ASK_LOCK.stat().st_mtime > max_wait + 120:
                    os.rmdir(ASK_LOCK)  # stale lock from a dead hook
                    continue
            except OSError:
                pass
            time.sleep(3)
    return "timeout"


def release_ask_lock():
    try:
        os.rmdir(ASK_LOCK)
    except OSError:
        pass

ENV = {
    **os.environ,
    "LARKSUITE_CLI_NO_UPDATE_NOTIFIER": "1",
    "LARKSUITE_CLI_NO_SKILLS_NOTIFIER": "1",
}

QUOTED_SPAN = re.compile(r"\"[^\"]*\"|'[^']*'")

ALLOW_WORDS = {"允许", "同意", "批准", "approve", "yes", "y", "ok"}
ALLOW_ALL_WORDS = {"全部允许", "放行", "全部放行", "allow all", "approve all", "yolo"}
DENY_WORDS = {"拒绝", "不允许", "不行", "deny", "no", "n"}


def strip_mentions(content, mentions):
    """People reply '@Bot 允许' — drop the mention before matching."""
    for mention in mentions or []:
        content = content.replace(f"@{mention.get('name', '')}", " ")
    return " ".join(content.split()).strip()


SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\||\n")
DEVNULL_REDIRECTS = re.compile(r"\d?>\s*/dev/null")
UNSAFE_SUBSTRINGS = ("$(", "`", ">", "<(")


def bash_is_read_only(command, prefixes):
    """True only when EVERY chained segment starts with an allowed read prefix.

    Agents habitually write `cd x && ls && cat y` — plain prefix matching sees
    only the `cd` and gates a pure read. Split on the chain operators and check
    each piece; command substitution / backticks / redirects (except >/dev/null)
    fail closed, since they can smuggle writes into a read-looking command.
    """
    cleaned = DEVNULL_REDIRECTS.sub(" ", command)
    if any(marker in cleaned for marker in UNSAFE_SUBSTRINGS):
        return False
    # Quoted text is data, not shell syntax: a | inside --pretty=format:"%an|%s"
    # is not a pipe. Blank quoted spans out (AFTER the unsafe check above, so
    # nothing dangerous can hide in them) before splitting into segments.
    cleaned = QUOTED_SPAN.sub("''", cleaned)
    segments = [segment.strip() for segment in SEGMENT_SPLIT.split(cleaned)]
    checked = 0
    for segment in segments:
        if not segment:
            continue
        if not any(segment == p or segment.startswith(p + " ") for p in prefixes):
            return False
        checked += 1
    return checked > 0


def lark(*args, timeout=60):
    try:
        proc = subprocess.run(
            ["lark-cli", *args], capture_output=True, text=True,
            timeout=timeout, env=ENV,
        )
        raw = proc.stdout.strip() or proc.stderr.strip()
        return json.loads(raw) if raw else {"ok": False}
    except Exception:  # noqa: BLE001
        return {"ok": False}


def decide(allow, reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow" if allow else "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


STYLE = os.environ.get("TTMA_REPLY_STYLE", "thread")
CHAT_ID = os.environ.get("TTMA_CHAT_ID", "")


def post(trigger_id, text):
    args = ["im", "+messages-reply", "--as", "bot", "--message-id", trigger_id]
    if STYLE != "chat":
        args.append("--reply-in-thread")
    args += ["--text", text]
    return lark(*args)


def recent_messages(trigger_id):
    """Where we look for the owner's 允许/拒绝: the thread, or the chat itself."""
    if STYLE == "chat" and CHAT_ID:
        envelope = lark("im", "+chat-messages-list", "--as", "user",
                        "--chat-id", CHAT_ID, "--order", "desc", "--page-size", "20")
    else:
        envelope = lark("im", "+threads-messages-list", "--thread", trigger_id, "--order", "desc")
    return (envelope.get("data") or {}).get("messages") or []


def main():
    payload = json.load(sys.stdin)
    tool = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}
    session_id = payload.get("session_id") or ""

    # Owner-level blanket grants: +free on the summon, or a prior 全部允许.
    if os.environ.get("TTMA_GRANT_ALL") == "1":
        decide(True, "owner pre-granted this run (+free)")
    if session_id and (GRANTS_DIR / session_id).exists():
        decide(True, "owner granted the whole session")

    auto_tools = set(filter(None, (os.environ.get("TTMA_AUTO_ALLOW_TOOLS") or "").split(",")))
    auto_bash = [p.strip() for p in (os.environ.get("TTMA_AUTO_ALLOW_BASH") or "").split(",") if p.strip()]
    roots = [r for r in (os.environ.get("TTMA_ALLOWED_READ_ROOTS") or "").split(":") if r]

    def path_in_roots(path):
        """Reads inside the allowed roots are free; anywhere else asks the owner."""
        if not roots:
            return True
        real = os.path.realpath(os.path.expanduser(path))
        return any(real == root or real.startswith(root + "/") for root in roots)

    if tool in auto_tools:
        candidate = tool_input.get("file_path") or tool_input.get("path") or ""
        if not candidate or path_in_roots(candidate):
            decide(True, "read-only tool in allowed scope")
    if tool == "Bash":
        command = (tool_input.get("command") or "").strip()
        if bash_is_read_only(command, auto_bash):
            cleaned = DEVNULL_REDIRECTS.sub(" ", command)
            candidates = [
                piece
                for token in cleaned.replace('"', " ").replace("'", " ").split()
                for piece in token.split("=")
                if piece.startswith(("/", "~"))
            ]
            if all(path_in_roots(p) for p in candidates):
                decide(True, "read-only command in allowed scope")

    trigger = os.environ.get("TTMA_TRIGGER_MSG_ID")
    owner = os.environ.get("TTMA_OWNER_OPEN_ID")
    timeout_s = int(os.environ.get("TTMA_APPROVAL_TIMEOUT", "300"))
    if not trigger or not owner:
        decide(False, "no approval channel configured — denied by default")

    # Serialize asks: only one 🔐 outstanding at a time across parallel tool
    # calls, so a single 允许 answers exactly one ask instead of all of them.
    # A blanket grant landing while we wait lets us skip asking entirely.
    outcome = acquire_ask_lock(timeout_s * 2, session_id)
    if outcome == "granted":
        decide(True, "owner granted the whole session")
    if outcome == "timeout":
        decide(False, "approval queue congested — denied")
    atexit.register(release_ask_lock)  # decide() exits via sys.exit; release either way

    # Snapshot BEFORE asking, so old 允许/拒绝 messages can't leak in.
    baseline = {m.get("message_id") for m in recent_messages(trigger)}

    compact = json.dumps(tool_input, ensure_ascii=False)
    if len(compact) > 280:
        compact = compact[:280] + "…"
    where = "回复" if STYLE == "chat" else "在本 thread 回复"
    post(
        trigger,
        f'<at user_id="{owner}"></at> 🔐 需要授权才能继续:\n{tool} {compact}\n'
        f"{where}「允许」(仅此条) /「全部允许」(本次任务不再问) /「拒绝」"
        f"({timeout_s}s 超时自动拒绝)",
    )

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        time.sleep(6)
        for message in recent_messages(trigger):
            if message.get("message_id") in baseline:
                continue
            sender = message.get("sender") or {}
            if sender.get("sender_type") != "user" or sender.get("id") != owner:
                continue
            text = strip_mentions(
                str(message.get("content") or ""), message.get("mentions"),
            ).lower()
            if text in ALLOW_ALL_WORDS or any(text.startswith(w) for w in ("全部允许", "放行")):
                if session_id:
                    GRANTS_DIR.mkdir(parents=True, exist_ok=True)
                    (GRANTS_DIR / session_id).write_text("granted")
                decide(True, "owner granted the whole session")
            if text in ALLOW_WORDS or any(text.startswith(w) for w in ("允许", "同意", "批准")):
                decide(True, "owner approved in thread")
            if text in DENY_WORDS or any(text.startswith(w) for w in ("拒绝", "不允许", "不行")):
                decide(False, "owner denied in thread")

    post(trigger, "⏳ 授权超时,该操作已自动拒绝。")
    decide(False, f"approval timed out after {timeout_s}s")


if __name__ == "__main__":
    main()
