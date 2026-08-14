#!/usr/bin/env python3
"""PreToolUse hook: the summoned agent's permission gate.

Read-only tools pass instantly. Anything else posts an approval request into
the Feishu thread that summoned the agent, and waits for the OWNER (and only
the owner) to reply 允许 / 拒绝. Timeout means deny.

Claude Code invokes this with the tool call as JSON on stdin; we answer with
a permissionDecision on stdout. Context arrives via TTMA_* environment
variables set by bridge.py.
"""

import json
import os
import subprocess
import sys
import time

ENV = {
    **os.environ,
    "LARKSUITE_CLI_NO_UPDATE_NOTIFIER": "1",
    "LARKSUITE_CLI_NO_SKILLS_NOTIFIER": "1",
}

ALLOW_WORDS = {"允许", "同意", "批准", "approve", "yes", "y", "ok"}
DENY_WORDS = {"拒绝", "不允许", "不行", "deny", "no", "n"}


def strip_mentions(content, mentions):
    """People reply '@Bot 允许' — drop the mention before matching."""
    for mention in mentions or []:
        content = content.replace(f"@{mention.get('name', '')}", " ")
    return " ".join(content.split()).strip()


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


def thread_messages(trigger_id):
    envelope = lark("im", "+threads-messages-list", "--thread", trigger_id, "--order", "desc")
    return (envelope.get("data") or {}).get("messages") or []


def main():
    payload = json.load(sys.stdin)
    tool = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}

    auto_tools = set(filter(None, (os.environ.get("TTMA_AUTO_ALLOW_TOOLS") or "").split(",")))
    auto_bash = [p.strip() for p in (os.environ.get("TTMA_AUTO_ALLOW_BASH") or "").split(",") if p.strip()]

    if tool in auto_tools:
        decide(True, "read-only tool")
    if tool == "Bash":
        command = (tool_input.get("command") or "").strip()
        if any(command == p or command.startswith(p + " ") for p in auto_bash):
            decide(True, "read-only command")

    trigger = os.environ.get("TTMA_TRIGGER_MSG_ID")
    owner = os.environ.get("TTMA_OWNER_OPEN_ID")
    timeout_s = int(os.environ.get("TTMA_APPROVAL_TIMEOUT", "300"))
    if not trigger or not owner:
        decide(False, "no approval channel configured — denied by default")

    # Snapshot the thread BEFORE asking, so old 允许/拒绝 messages can't leak in.
    baseline = {m.get("message_id") for m in thread_messages(trigger)}

    compact = json.dumps(tool_input, ensure_ascii=False)
    if len(compact) > 280:
        compact = compact[:280] + "…"
    lark(
        "im", "+messages-reply", "--as", "bot", "--message-id", trigger,
        "--reply-in-thread", "--text",
        f"🔐 需要授权才能继续:\n{tool} {compact}\n"
        f"owner 在本 thread 回复「允许」或「拒绝」({timeout_s}s 超时自动拒绝)",
    )

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        time.sleep(6)
        for message in thread_messages(trigger):
            if message.get("message_id") in baseline:
                continue
            sender = message.get("sender") or {}
            if sender.get("sender_type") != "user" or sender.get("id") != owner:
                continue
            text = strip_mentions(
                str(message.get("content") or ""), message.get("mentions"),
            ).lower()
            if text in ALLOW_WORDS or any(text.startswith(w) for w in ("允许", "同意", "批准")):
                decide(True, "owner approved in thread")
            if text in DENY_WORDS or any(text.startswith(w) for w in ("拒绝", "不允许", "不行")):
                decide(False, "owner denied in thread")

    lark(
        "im", "+messages-reply", "--as", "bot", "--message-id", trigger,
        "--reply-in-thread", "--text", "⏳ 授权超时,该操作已自动拒绝。",
    )
    decide(False, f"approval timed out after {timeout_s}s")


if __name__ == "__main__":
    main()
