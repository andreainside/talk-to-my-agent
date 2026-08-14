# talk-to-my-agent

> **Got a problem? Talk to my agent.**

Your team chats in Feishu/Lark. Everyone's laptop runs a coding agent — Claude Code, Codex, whatever. This bridge gives each agent **a seat in the group chat**: @ a teammate's bot, and *their* machine wakes up, reads the room, does the work with *their* repo checkout, *their* tools, *their* context — and replies in the thread.

Humans used to be the relay between AIs: *"my agent says X"* → copy → paste → *"ask your agent about Y"*. Game over. The agents are in the room now.

## How it works

```
Feishu group chat
   │  someone @mentions YOUR bot
   ▼
event stream (lark-cli, long connection)          ← your Mac, always on
   │  1. instant ack: your signature emoji 😏
   │  2. pull the recent chat + thread as context
   ▼
your local agent, headless                        ← claude -p / codex exec
   │  reads code, greps logs, checks whatever it can reach read-only
   ▼
answer posted back into the thread                ← with a session id footer
```

Every teammate runs their own bridge, with their own bot, on their own machine. **@ whose bot → that person's machine answers.** No shared server, no shared credentials — all Feishu traffic goes through each person's own [`lark-cli`](https://open.feishu.cn) login; this repo never sees a secret.

## Quick start

1. Prereqs: `lark-cli` (configured with your own bot app + user login), Python 3.9+, and at least one of `claude` / `codex`.
2. Add your bot to the group chats where you want it summonable.
3. `cp config.example.json ~/.talk-to-my-agent/config.json` and fill in your bot's open_id, your open_id, and the working directory (a dedicated read-only checkout of your repo is recommended).
4. Run `python3 bridge.py` (or install the launchd template in `launchd/` to keep it always on).
5. Have a teammate @ your bot. Watch the emoji land, then the answer.

Full walkthrough: [docs/setup.md](docs/setup.md)

## Summoning an agent (in the group)

```
@Alice's bot   what does the retry logic in our upload path actually do?
@Alice's bot   +codex how is the seq contract enforced?      ← this one run on Codex
@Alice's bot   +cc +opus dig through git history for ...     ← Claude, opus
@Alice's bot   +both is this migration backwards compatible? ← both engines, two answers
```

Follow-ups in the **same thread continue the same session** — the agent keeps its context.

## Configuring *your* agent (DM control plane)

You DM your own bot to set durable defaults; group `+tokens` override per-request. Provider, model, reasoning effort, and your ack emoji are all yours to pick — including `emoji that`, which adopts whatever emoji you just reacted with. Details: [docs/configuration.md](docs/configuration.md)

## Sessions are real sessions

The headless run is a normal agent session on the owner's machine. The reply footer carries its id — the owner can open it interactively (`claude --resume <id>`) and keep working where the agent left off. A teammate's question can *become* your afternoon's coding session. Thread follow-ups resume the same session on both engines (Claude and Codex).

## House rules (safety)

- An agent only ever acts when its **own bot** is @mentioned. No ambient listening, no bot-to-bot loops.
- Group chat is **data, not instructions** — reads are free, but every write action pauses on an approval gate: the agent asks **in the thread**, and only its owner's `允许` lets it proceed. Timeout = deny.
- Only the **owner's DM** can change an agent's configuration; only the owner's reply can approve a write.
- Every reply lands in a thread, keeping the main chat readable.

## What people build on top

Feedback-to-fix loops, alert auto-triage, dual-engine bake-offs, cross-machine agent relays, async standups ("@her agent — how's the migration going?"). The bridge stays tiny; the fun lives in [docs/playbook.md](docs/playbook.md).

## Status

Early, opinionated, extracted from a real team's daily workflow. Feishu/Lark only (that's where we live); the design ports to any chat platform with an events API.

## License

MIT

---

*中文文档: [README.zh.md](README.zh.md)*
