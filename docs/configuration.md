# Configuration

Two layers: **durable settings live in your DM with your own bot**, and the file
`~/.talk-to-my-agent/config.json` holds the per-machine wiring. Nobody but you
can reconfigure your agents.

## 1. DM control plane

DM your own bot. Commands are plain text:

| Command | Effect |
|---|---|
| `status` | who's on staff (one agent per group), what each is doing, cost so far |
| `model opus` / `sonnet` / `haiku` | switch everyone's model; sessions and memory survive |
| `emoji SMUG` | the emoji your bot drops when summoned |
| `emoji that` | react on the bot's last DM message, then send this — it adopts that emoji |
| `reset <group>` / `reset all` | fresh brain for that group's agent (its notes stay) |
| `help` | command list |

Emoji keys are Feishu's fixed reaction keys (`Yes`, `No`, `CheckMark`, `SMUG`,
`THUMBSUP`, …). They aren't guessable from the picker, so `emoji that` is the
reliable route: react with the face you want, then send the command.

## 2. Permissions: zones, not command lists

An agent is free inside a workspace and asks about anything beyond it. There is
no allowlist of "safe commands" to maintain — that approach breaks on every new
shell idiom.

| Zone | What's in it | What the agent may do |
|---|---|---|
| **write zone** | its own home, your `workdir` (use a *disposable* checkout), the engine's scratch dir | read, write, run — freely |
| **read zone** | the write zone, every agent's home, plus `allowed_read_roots` | read freely; changing things here asks |
| everywhere else | your other files, `~/.ssh`, the system | asks |

On top of that, two short semantic rules:

- **Destructive actions** (`rm`, `mv`, overwriting redirects, `sed -i`,
  `git reset/clean/checkout --`, `chmod`, …) are free inside the write zone —
  deleting build output in a throwaway worktree is just work — but **ask**
  whenever they reach outside it.
- **Outward or irreversible actions** (`git push`, `gh pr create/merge`,
  `npm/cargo publish`, `kubectl apply`, `terraform apply`, `docker push`,
  mutating `curl`) **always ask**, even under a blanket grant. You can undo a
  bad local edit; you cannot unpublish.

Run `python3 test_permissions.py` to see the whole policy as executable cases.

**Known limitation, stated plainly**: a command can compute paths at runtime
(`python -c ...`), and no text-level gate can see that. Real containment needs
an OS sandbox — that's future hardening, not something this gate pretends to do.
The threat model it does cover: an agent doing something careless, and prompt
injection arriving through chat.

## 3. Answering an approval card

The card says what the agent wants in plain words, with the technical detail
below it. Only the **owner's** response counts (verified by open_id):

- **YES** — allow this one action
- **✔** — allow everything for the rest of this task (outward actions still ask)
- **NO** — refuse
- silence — timeout (default 5 min) refuses

Typing `允许` / `全部允许` / `拒绝` works the same; @-ing the bot in your reply is
fine. `@bot +free <request>` pre-grants a whole task up front — owner only.

## 4. `config.json` (per machine, never committed)

```jsonc
{
  "backend": "claude",            // "claude" or "codex" — whichever you run
  "bot_open_id":   "ou_...",      // your bot   (lark-cli auth status → identities.bot.openId)
  "owner_open_id": "ou_...",      // you        (→ identities.user.openId)
  "workdir": "~/work/agent-tree", // where agents run; a checkout dedicated to them
  "workdir_sync_command": "git fetch -q origin && git reset -q --hard origin/main",
                                   // keeps the workdir == GitHub latest at task start; "" disables
  "allowed_read_roots": [],       // extra dirs they may read freely (your repos)
  "allowed_write_roots": [],      // extra dirs they may change freely (rare)
  "context_messages": 20,          // how much backlog a brand-new agent reads
  "ack_emoji": "THUMBSUP",        // until you set your own via DM
  "model": "",                     // "" = engine default; DM `model opus` to change
  "reply_style": "chat",          // "chat" = main flow, "thread" = threaded replies
  "approvals": { "enabled": true, "timeout_seconds": 300 },
  "max_bot_chain": 3,              // consecutive agent→agent messages before it stops
  "env_file": "~/.talk-to-my-agent/env",   // CLAUDE_CODE_OAUTH_TOKEN, proxies (chmod 600)
  "groups": []                     // chat_id allowlist; empty = every group the bot is in
}
```

`workdir` should be a checkout you don't personally edit — agents write there
without asking, and `workdir_sync_command` (default: fetch + hard-reset to
origin/main) runs whenever a task starts while no agent is busy, so agents
always diagnose against GitHub's latest, never a stale checkout. Set it to ""
for a non-git workdir. Your real working tree belongs in `allowed_read_roots`
instead: readable, but changes ask — and the workspace briefing tells agents
it may be behind or mid-edit, so code questions are answered from their own
synced repository.

## 5. Backends: Claude Code or Codex

Set `"backend"` and run whichever CLI you have. Same colleague-per-group model,
same approval policy, same chat behaviour — with two honest differences:

| | Claude Code | Codex |
|---|---|---|
| memory file in each home | `CLAUDE.md` | `AGENTS.md` |
| asked mid-task, during a long blocking command | answers right away (it backgrounds long commands) | answers at its next reasoning boundary — after the command finishes |
| containment | the policy gate (text-level) | an OS sandbox limited to the write zone, plus the same policy gate on escalation |
| model switching | `model opus` / `sonnet` / `haiku` | set `"model"` in the config |

Codex gets **stronger containment** (a real sandbox, network off inside it —
anything reaching out becomes an approval request) and a **weaker interruption
promise**. Pick accordingly; the rest is identical.

Codex's app-server protocol is marked experimental upstream. Pin your CLI
version, and re-run `python3 test_permissions.py` plus a live summon after
upgrading it.

## 6. State on disk

`~/.talk-to-my-agent/`

- `home/<group>/CLAUDE.md` — each agent's long-term memory, written by itself
- `home/shared/` — material every agent can read
- `state.json` — session ids, watermarks, costs, your DM preferences
- `grants/`, `summons/`, `approval.lock` — approval bookkeeping
- `env` — headless auth token and proxies

Deleting `state.json` makes everyone a new hire; their notes survive.
