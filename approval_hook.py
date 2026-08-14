#!/usr/bin/env python3
"""PreToolUse hook: the permission gate for a summoned agent.

The model is **zones, not command classification**. We never try to decide
whether a command "looks read-only" — that's an open-ended set and enumerating
its surface forms breaks on every new shell idiom. Instead:

  write zone   the agent's home + the dedicated (disposable) worktree + scratch
               → it may read, write and run anything here
  read zone    the write zone + the repos the owner opened up
               → it may read freely; changing things here asks
  outside      → asks

Each ask posts its own card and is answered on that card (a tap, or a reply),
so parallel asks never steal each other's verdict.

plus two short, *semantic* lists: destructive verbs (only matter outside the
write zone) and outward/irreversible actions (always ask, even under a blanket
grant, because pushing or publishing cannot be undone by the owner later).

Known limitation: a command can compute paths at runtime (`python -c ...`), and
no text-level gate can see that. Real containment needs an OS sandbox; that is
future hardening, documented rather than pretended away.

Claude Code invokes this with the tool call as JSON on stdin; we answer with a
permissionDecision on stdout. Context arrives via TTMA_* environment variables.
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

STATE_DIR = Path(os.environ.get("TTMA_HOME", Path.home() / ".talk-to-my-agent"))
GRANTS_DIR = STATE_DIR / "grants"

ENV = {
    **os.environ,
    "LARKSUITE_CLI_NO_UPDATE_NOTIFIER": "1",
    "LARKSUITE_CLI_NO_SKILLS_NOTIFIER": "1",
}

STYLE = os.environ.get("TTMA_REPLY_STYLE", "thread")

# ---------------------------------------------------------------- policy --

READ_TOOLS = {"Read", "Grep", "Glob", "LS", "NotebookRead"}
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

# Things that change or destroy what they touch. They only matter outside the
# write zone — inside a disposable worktree, deleting is just working.
DESTRUCTIVE = re.compile(
    r"(?:^|[\s;&|(])(?:rm|rmdir|mv|cp|dd|truncate|tee|shred|chmod|chown|ln|"
    r"install|mkfs|unlink)(?:\s|$)"
    r"|(?:^|[\s;&|(])sed\s+[^|;&]*-i"
    r"|(?:^|[\s;&|(])perl\s+[^|;&]*-i"
    r"|git\s+(?:reset|clean|checkout\s+--|restore|rm|branch\s+-[dD]|stash\s+(?:drop|clear))"
    r"|>{1,2}\s*[^\s|&]",
)

# Actions that leave this machine or cannot be undone from the owner's chair.
# These ask even under +free / 全部允许 — a blanket grant is about convenience
# inside the workspace, not about publishing.
OUTWARD = re.compile(
    r"git\s+push|git\s+remote\s+(?:add|remove|set-url)"
    r"|gh\s+(?:pr\s+(?:create|merge|close|edit|review)|release|repo\s+(?:create|delete)|api\s)"
    r"|(?:npm|pnpm|yarn|cargo|gem|twine)\s+publish|npm\s+deprecate"
    r"|(?:kubectl|helm)\s+(?:apply|delete|rollout)|terraform\s+(?:apply|destroy)"
    r"|docker\s+push|gcloud\s+\w+\s+deploy|aws\s+\w+\s+(?:put|delete|create)"
    r"|curl\s[^|;&]*(?:-X\s*(?:POST|PUT|PATCH|DELETE)|--data|-d\s)"
    r"|wget\s[^|;&]*--post",
    re.IGNORECASE,
)

# A path only counts when the / or ~ starts a token — otherwise `target/debug`
# would read as the absolute path `/debug` and gate an ordinary build cleanup.
PATH_TOKEN = re.compile(r"""(?:^|[\s'"=:(,;&|<>])((?:~|/)[\w./@%+:=-]*)""")


def zones():
    def parse(name):
        return [os.path.realpath(os.path.expanduser(p))
                for p in (os.environ.get(name) or "").split(":") if p]
    return parse("TTMA_WRITE_ZONE"), parse("TTMA_READ_ZONE")


def under(path, roots):
    if not roots:
        return False
    real = os.path.realpath(os.path.expanduser(path))
    return any(real == root or real.startswith(root + "/") for root in roots)


def command_paths(command):
    """Absolute/tilde paths mentioned anywhere in the command — including inside
    quotes and substitutions. We scan rather than parse: structure is what kept
    breaking, and a stray path is exactly what we care about."""
    found = []
    for match in PATH_TOKEN.finditer(command):
        token = match.group(1).rstrip(":;,)\"'")
        if token in ("/", "~") or len(token) < 2:
            continue
        if token.startswith("/dev/") or token.startswith("/proc/"):
            continue
        found.append(token)
    return found


# ------------------------------------------------------------------- chat --

def lark(*args, timeout=60):
    try:
        proc = subprocess.run(["lark-cli", *args], capture_output=True, text=True,
                              timeout=timeout, env=ENV)
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


def summon_context():
    """Which chat message the agent is currently answering. The agent process is
    long-lived, so the bridge writes the current summon to a file per chat."""
    trigger = os.environ.get("TTMA_TRIGGER_MSG_ID", "")
    chat_id = os.environ.get("TTMA_CHAT_ID", "")
    summons = sorted((STATE_DIR / "summons").glob("*.json"),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    for path in summons:
        try:
            data = json.loads(path.read_text())
        except Exception:  # noqa: BLE001
            continue
        return data.get("TTMA_TRIGGER_MSG_ID", trigger), data.get("TTMA_CHAT_ID", chat_id)
    return trigger, chat_id


def post(trigger_id, text):
    args = ["im", "+messages-reply", "--as", "bot", "--message-id", trigger_id]
    if STYLE != "chat":
        args.append("--reply-in-thread")
    args += ["--text", text]
    return lark(*args)


def recent_messages(trigger_id, chat_id=""):
    if STYLE == "chat" and chat_id:
        envelope = lark("im", "+chat-messages-list", "--as", "user",
                        "--chat-id", chat_id, "--order", "desc", "--page-size", "20")
    else:
        envelope = lark("im", "+threads-messages-list", "--thread", trigger_id, "--order", "desc")
    return (envelope.get("data") or {}).get("messages") or []


def strip_mentions(content, mentions):
    for mention in mentions or []:
        content = content.replace(f"@{mention.get('name', '')}", " ")
    return " ".join(content.split()).strip()


ALLOW_WORDS = {"允许", "同意", "批准", "approve", "yes", "y", "ok"}
ALLOW_ALL_WORDS = {"全部允许", "放行", "全部放行", "allow all", "approve all", "yolo"}
DENY_WORDS = {"拒绝", "不允许", "不行", "deny", "no", "n"}
YES_EMOJI = {"Yes", "THUMBSUP", "OK", "DONE"}
NO_EMOJI = {"No", "CROSS", "THUMBSDOWN"}
ALL_EMOJI = {"CheckMark", "GreenCheckMark"}


def reaction_verdict(message_id, owner):
    envelope = lark("im", "reactions", "list", "--as", "bot",
                    "--params", json.dumps({"message_id": message_id}))
    for item in (envelope.get("data") or {}).get("items") or []:
        operator = item.get("operator") or {}
        if operator.get("operator_type") == "app" or operator.get("operator_id") != owner:
            continue
        key = (item.get("reaction_type") or {}).get("emoji_type")
        if key in ALL_EMOJI:
            return "all"
        if key in YES_EMOJI:
            return "yes"
        if key in NO_EMOJI:
            return "no"
    return None


def humanize(tool, tool_input, why):
    """Plain language first — the agent's own description when it wrote one."""
    described = (tool_input.get("description") or "").strip()
    path = tool_input.get("file_path") or tool_input.get("path") or ""
    if described:
        headline = described
    elif tool in WRITE_TOOLS:
        headline = f"修改文件 {path}" if path else "修改文件"
    elif tool in READ_TOOLS:
        headline = f"读取 {path}" if path else "读取文件"
    elif tool == "Bash":
        headline = "执行一条命令"
    elif tool == "WebFetch":
        headline = f"访问 {tool_input.get('url', '')}"
    else:
        headline = f"使用 {tool}"
    detail = str(tool_input.get("command") or path or json.dumps(tool_input, ensure_ascii=False))
    if len(detail) > 200:
        detail = detail[:200] + "…"
    return f"{headline}({why})", detail


def ask_text(owner, tool, tool_input, why, timeout_s):
    headline, detail = humanize(tool, tool_input, why)
    minutes = max(1, timeout_s // 60)
    return (
        f'<at user_id="{owner}"></at> 🔐 我想{headline},可以吗?\n'
        f"点 YES 同意这一次 · 点 ✔ 本次任务都不用再问 · 点 NO 不同意\n"
        f"({minutes} 分钟没回应就当作不同意)\n"
        f"技术细节:{tool} {detail}"
    )


# ------------------------------------------------------------ ask plumbing --

def grant_session(session_id):
    if session_id:
        GRANTS_DIR.mkdir(parents=True, exist_ok=True)
        (GRANTS_DIR / session_id).write_text("granted")


def ask_owner(tool, tool_input, why, session_id, blanket_ok=True):
    trigger, chat_id = summon_context()
    owner = os.environ.get("TTMA_OWNER_OPEN_ID")
    timeout_s = int(os.environ.get("TTMA_APPROVAL_TIMEOUT", "300"))
    if not trigger or not owner:
        decide(False, "no approval channel configured — denied by default")

    if blanket_ok and session_id and (GRANTS_DIR / session_id).exists():
        decide(True, "owner granted the whole task")

    baseline = {m.get("message_id") for m in recent_messages(trigger, chat_id)}
    result = post(trigger, ask_text(owner, tool, tool_input, why, timeout_s))
    ask_id = (result.get("data") or {}).get("message_id")

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        time.sleep(5)
        verdict = reaction_verdict(ask_id, owner) if ask_id else None
        if verdict == "all":
            if blanket_ok:
                grant_session(session_id)
            decide(True, "owner tapped ✔")
        if verdict == "yes":
            decide(True, "owner tapped YES")
        if verdict == "no":
            decide(False, "owner tapped NO")
        for message in recent_messages(trigger, chat_id):
            if message.get("message_id") in baseline:
                continue
            sender = message.get("sender") or {}
            if sender.get("sender_type") != "user" or sender.get("id") != owner:
                continue
            text = strip_mentions(str(message.get("content") or ""), message.get("mentions")).lower()
            if text in ALLOW_ALL_WORDS or any(text.startswith(w) for w in ("全部允许", "放行")):
                if blanket_ok:
                    grant_session(session_id)
                decide(True, "owner granted the whole task")
            if text in ALLOW_WORDS or any(text.startswith(w) for w in ("允许", "同意", "批准")):
                decide(True, "owner approved")
            if text in DENY_WORDS or any(text.startswith(w) for w in ("拒绝", "不允许", "不行")):
                decide(False, "owner denied")

    post(trigger, "⏳ 授权超时,该操作已自动拒绝。")
    decide(False, f"approval timed out after {timeout_s}s")


# ------------------------------------------------------------------- main --

def main():
    payload = json.load(sys.stdin)
    tool = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}
    session_id = payload.get("session_id") or ""
    write_zone, read_zone = zones()

    command = str(tool_input.get("command") or "") if tool == "Bash" else ""

    # 1. Outward / irreversible: always ask, blanket grants do not cover it.
    if command and OUTWARD.search(command):
        ask_owner(tool, tool_input, "会推送到外部或不可撤销", session_id, blanket_ok=False)

    # 2. Blanket grants cover everything else.
    if os.environ.get("TTMA_GRANT_ALL") == "1":
        decide(True, "owner pre-granted this task (+free)")
    if session_id and (GRANTS_DIR / session_id).exists():
        decide(True, "owner granted the whole task")

    # 3. File tools: read zone to look, write zone to change.
    path = tool_input.get("file_path") or tool_input.get("path") or ""
    if tool in READ_TOOLS:
        if not path or under(path, read_zone):
            decide(True, "reading inside the read zone")
        ask_owner(tool, tool_input, "这个位置不在我平时能读的范围里", session_id)
    if tool in WRITE_TOOLS:
        if path and under(path, write_zone):
            decide(True, "writing inside the write zone")
        ask_owner(tool, tool_input, "要改的东西在我的工作区之外", session_id)

    # 4. Shell: only two questions — does it reach outside, and would that hurt?
    if command:
        paths = command_paths(command)
        outside_read = [p for p in paths if not under(p, read_zone)]
        if outside_read:
            ask_owner(tool, tool_input,
                      f"要碰工作区外的 {outside_read[0]}", session_id)
        if DESTRUCTIVE.search(command):
            outside_write = [p for p in paths if not under(p, write_zone)]
            if outside_write:
                ask_owner(tool, tool_input,
                          f"是会改动/删除的操作,而且碰到 {outside_write[0]}", session_id)
        decide(True, "stays inside the workspace")

    # 5. Everything else (search, notes, MCP calls the owner installed).
    decide(True, f"{tool}: no filesystem or outward effect to gate")


if __name__ == "__main__":
    main()
