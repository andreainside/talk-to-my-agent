# Configuration

Two layers, one principle: **durable defaults live in your DM with your own bot; group `+tokens` are one-shot overrides and never persist.** Nobody but you can reconfigure your agent.

## 1. DM control plane (durable — 私聊设默认值)

DM your own bot. Commands are plain text:

| Command | Effect |
|---|---|
| `status` | show provider / model / effort / ack emoji / workdir |
| `model claude` | switch provider to Claude Code |
| `model claude opus` | provider + model (`opus` / `sonnet` / `haiku`) |
| `model codex` | switch provider to Codex |
| `model codex gpt-5-codex` | provider + any model name Codex accepts via `-m` |
| `effort low` / `effort medium` / `effort high` | reasoning effort |
| `emoji SMUG` | set the ack emoji your bot drops when summoned |
| `emoji that` | adopt whatever emoji **you just reacted** on the bot's last DM message |
| `help` | command list |

Notes:

- **Effort** is passed where the provider supports it (Codex: `model_reasoning_effort`). For Claude Code, strength is chosen via the model (`opus` > `sonnet` > `haiku`); an unsupported effort setting is silently ignored, never an error.
- **Emoji keys** are Feishu's fixed reaction keys (`THUMBSUP`, `SMUG`, `OK`, …). Keys aren't guessable from the picker, so the reliable flow is `emoji that`: react on the bot's last message with the face you want, then send `emoji that` — the bridge reads the reaction back and adopts its key.

## 2. Group one-shot overrides (单次覆盖)

Tokens go right after the @mention, before the request:

```
@Alice's bot +codex           ...        run this one on Codex
@Alice's bot +cc              ...        run this one on Claude Code
@Alice's bot +both            ...        run on both, two answers
@Alice's bot +opus / +sonnet / +haiku    Claude model for this run
@Alice's bot +high / +medium / +low      effort for this run
@Alice's bot +model:gpt-5-codex          explicit model name for this run
```

Unrecognized leading `+tokens` end token parsing and become part of the request, so a message like "+1 to that idea" still reads naturally.

## 3. `config.json` (per machine, never committed)

```jsonc
{
  "bot_open_id":  "ou_...",       // your bot's open_id  (lark-cli auth status)
  "owner_open_id": "ou_...",      // your own open_id — the only DM the bridge obeys
  "workdir": "~/work/my-repo",    // where headless agents run; use a dedicated checkout
  "context_messages": 40,          // how much recent chat the agent gets to read
  "ack_emoji": "THUMBSUP",        // default until you set your own via DM
  "executor": { "provider": "claude", "model": "", "effort": "" },
  "claude_args": ["--allowedTools", "Read,Grep,Glob,Bash(git log:*),Bash(git show:*),Bash(rg:*)"],
  "codex_args": ["--sandbox", "read-only"],
  "run_timeout_seconds": 900,
  "groups": []                     // chat_id allowlist; empty = every group the bot is in
}
```

The two `*_args` lists are the sandbox policy. Defaults are read-only on both engines; widen them only if you understand what a group member can then make your machine do.

## 4. State

`~/.talk-to-my-agent/state.json` holds your DM-set preferences, the thread→session map (that's what makes same-thread follow-ups continue the same session), and bookkeeping. Delete it any time; you only lose thread continuity.
