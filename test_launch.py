"""End-to-end launch check: does an agent actually come up and answer?

Two releases shipped broken because the checks only proved that a one-off
`claude -p` could see the repo — never that the bridge's own long-lived agent
survived its launch flags. It died in 0.2s, the bridge logged "started", and
the chat looked like an agent ignoring its owner.

Run before every release that touches agent startup:

    python3 test_launch.py

No Feishu traffic: chat calls are stubbed, the agent process is real.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

STATE = Path(tempfile.mkdtemp(prefix="ttma-launch-"))
os.environ["TTMA_HOME"] = str(STATE)
import bridge  # noqa: E402  (must follow TTMA_HOME)

CHAT = "oc_LAUNCHTEST"
failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def main():
    if not (shutil_which := __import__("shutil").which)("claude"):
        print("SKIP: claude not on PATH")
        return 0

    workdir = Path(os.environ.get("TTMA_LAUNCH_WORKDIR", tempfile.mkdtemp(prefix="ttma-work-")))
    (workdir / "CLAUDE.md").write_text(
        "# Test repo conventions\n\nThis project's build command is `make plumbus`.\n"
        "Always state the build command when asked how to build.\n")

    bridge.lark = lambda *a, **k: {"ok": True, "data": {"name": "Launch Test", "messages": []}}
    bridge.react = lambda *a, **k: None
    bridge.reply = lambda *a, **k: {"ok": True}

    cfg = {
        "bot_open_id": "ou_bot", "owner_open_id": "ou_owner",
        "workdir": str(workdir), "approvals": {"enabled": True, "timeout_seconds": 60},
        "env_file": os.path.expanduser("~/.talk-to-my-agent/env"),
        "reply_style": "chat", "allowed_read_roots": [],
    }
    cfg["_config_path"] = str(STATE / "config.json")
    cfg["_claude_settings_path"] = bridge.write_claude_settings(cfg)
    state = {"chat_names": {CHAT: "Launch Test"}}

    home = bridge.ensure_home(state, CHAT)
    (home / "CLAUDE.md").write_text(
        "# Who I am\n\nI hold a seat in a chat group. The group I sit in is called Rhombus Team.\n")

    agent = bridge.Agent(cfg, state, CHAT)
    agent.start()

    time.sleep(12)
    alive = agent.proc.poll() is None
    check("agent survives launch", alive,
          "" if alive else f"exited {agent.proc.poll()} — see {STATE/'agent-errors.log'}")
    if not alive:
        err = (STATE / "agent-errors.log")
        if err.exists():
            print("--- stderr ---"); print(err.read_text()[-800:])
        return 1

    # it must answer, and prove both context sources arrived.
    # Tap the bridge's own reader — a second thread on the same stdout would
    # race it and swallow half the stream (this test's first bug).
    answers = []
    agent.on_text = answers.append

    sent = agent.send("On one line, no tools: what is this project's build command, "
                      "and what is the name of the group you sit in?")
    check("bridge can write to the agent", sent)

    for _ in range(60):
        time.sleep(2)
        if answers:
            break
    reply_text = " ".join(answers)
    check("agent answers", bool(answers), reply_text[:80] if answers else "no reply in 120s")
    check("repo rules reached it (cwd)", "PLUMBUS" in reply_text.upper(),
          "repo CLAUDE.md not loaded" if "PLUMBUS" not in reply_text.upper() else "")
    check("own memory reached it (home)", "RHOMBUS" in reply_text.upper(),
          "home notes not loaded" if "RHOMBUS" not in reply_text.upper() else "")
    check("still alive after a task", agent.proc.poll() is None)

    agent.restart()
    return 1 if failures else 0


if __name__ == "__main__":
    code = main()
    print("\n" + ("LAUNCH OK" if code == 0 else f"LAUNCH BROKEN: {', '.join(failures)}"))
    sys.exit(code)
