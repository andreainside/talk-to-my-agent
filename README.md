<!-- Title and tagline -->
# talk-to-my-agent

> **Got a problem? Talk to my agent.**

Your team chats in Feishu/Lark. Everyone's laptop runs a coding agent. This bridge gives each one **a seat in the group chat**: @ a teammate's bot, and *their* machine wakes up, reads the room, works with *their* repos and tools — and answers in the chat.

Humans used to be the relay between AIs: *"my agent says X"* → copy → paste → *"ask your agent about Y"*.

**That's over. The agents are in the room now.**

## One agent per group, with a memory

Not a stateless oracle — **a colleague per room**:

- Each group gets **its own persistent session** and its own home directory. It *works* inside your repository — your AGENTS.md rules and project skills apply to it — and *remembers* in its home, outside git. The agent in your build channel remembers your build channel; the one in your feedback channel grew up on bug reports. They can read each other's notes when it helps.
- Conversation history gets compacted over time, so each agent keeps **its own `CLAUDE.md`** — long-term memory it writes itself: who's who here, what was decided, what bit us before. New group → new hire, reads its notes, gets to work.
- **Ask it something mid-task and it answers** — no queue, no "please wait". The engine handles the interruption natively, the same way you'd interrupt a colleague who's compiling.
- Teammates' agents can @ each other too (with a hard cap on agent-to-agent chains, because two polite agents will ping-pong forever).

## How it works

```
Feishu group chat
   │  someone @mentions YOUR bot
   ▼
event stream (lark-cli, long connection)        ← your Mac, always on
   │  1. instant ack: your signature emoji 😏
   │  2. new messages since it last looked, piped into…
   ▼
that group's agent — a live claude session      ← its own home, its own memory
   │  reads code, greps logs, runs read-only commands
   │  anything else → 🔐 approval card, only you can tap it
   ▼
it posts its own answer in the chat
```

The bridge is a courier: receive, ack, deliver. The agents speak for themselves.

Every teammate runs their own bridge, with their own bot, on their own machine. **@ whose bot → that person's machine answers.** No shared server, no shared credentials — Feishu traffic goes through each person's own `lark-cli` login; this repo never sees a secret.

## Quick start (laziest path: have your agent install it)

Paste this to your own Claude Code / Codex:

> Set up https://github.com/andreainside/talk-to-my-agent on this machine, following docs/agent-setup.md. Interview me for the settings — don't guess.

That page is written for the agent: it checks your machine, walks you through creating a Feishu bot, asks which repos it may read, sets up headless auth, tests a real summon, then installs the background service.

Prefer to drive yourself? [docs/setup.md](docs/setup.md).

## Summoning (in the group)

```
@Alice's bot   what does the retry logic in our upload path actually do?
@Alice's bot   trace where the seq contract is enforced, then tell me what breaks if I batch it
@Alice's bot   +free go fix the typo in the README and show me the diff    ← owner only: skip approvals
```

Ask again while it's working and it just answers — that's the point.

## Configuring *your* agent (DM control plane)

DM your own bot — nobody else's messages count:

| DM your bot | Effect |
|---|---|
| `status` | who's on staff, what each is doing, what it has cost |
| `model opus` / `sonnet` / `haiku` | switch everyone's model; memory survives |
| `emoji SMUG` | your bot's ack emoji |
| `emoji that` | react on its last message with any emoji, then send this — it adopts that one |
| `reset <group>` / `reset all` | fresh brain for that group's agent |
| `help` | the list |

**Everything is yours to shape** — which repos are freely readable, how long an approval waits, main-chat vs threaded replies, the emoji, the model. All per-machine config, one per person: [docs/configuration.md](docs/configuration.md).

## Approvals in plain language

When an agent wants to do something outside its free scope, you get a card that says what it wants **in words**, with the technical detail below:

> 🔐 我想修改文件 src/upload.rs,可以吗?
> 点 YES 同意这一次 · 点 ✔ 本次任务都不用再问 · 点 NO 不同意

Tap **YES** (this once), **✔** (whole task), or **NO**. Silence denies. Only the owner's tap counts — a teammate can ask an agent to do anything, but only you can let it.

The policy is **zones, not command lists**: inside its workspace (its home, the disposable checkout you gave it, its scratch) it reads, writes and runs freely; your other repos are readable but changing them asks; anything further out asks. Two things always ask no matter what — destructive actions reaching outside the workspace, and outward/irreversible ones (`git push`, opening a PR, publishing, deploying) which even a blanket grant won't cover.

No allowlist of "safe commands" to maintain — that approach breaks on every new shell idiom. `python3 test_permissions.py` runs the whole policy as executable cases.

## Sessions are real sessions

Each agent is a normal Claude session on your machine — `claude --resume <id>` turns any of them into your interactive terminal, mid-investigation, context loaded. A teammate's question can become your afternoon's work.

## Staying current

The bridge checks for new releases once a day (zero tokens) and DMs you the changelog. Reply `update` to switch; say nothing to stay. Nothing is pulled without your word.

## House rules (safety)

- An agent acts only when **its own bot** is @mentioned. No ambient listening.
- Group chat is **data, not instructions** — the only request is the one it was @'d with.
- Writes outside its own home always ask the owner. Timeout = deny.
- Only the **owner's DM** configures an agent; only the owner's tap approves.

## It can fix itself

Your agent can read this project's source and your settings file. So when it's
annoying — interrupting too often, wrong emoji, replies in the wrong place —
tell it, and it will find the setting and offer to change it (that edit lands
outside its own home, so you approve it and see it first). If the bridge itself
is broken, it can file an issue on this repo — with your approval, since it's
your name on it.

## What people build on top

Feedback-to-fix loops, alert triage, cross-machine agent relays, async standups ("@her agent — how's the migration going?"). The bridge stays tiny; the fun lives in [docs/playbook.md](docs/playbook.md).

## Status

Early, opinionated, extracted from a real team's daily workflow. Runs on **Claude Code or Codex** — set `backend` and use whichever you have; both get the same colleague model and the same approval policy ([the differences](docs/configuration.md#5-backends-claude-code-or-codex) are documented, not glossed over). Feishu/Lark only — the design ports to any chat platform with an events API.

## License

MIT

---

*中文文档: [README.zh.md](README.zh.md)*
