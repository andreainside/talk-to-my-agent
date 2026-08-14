# Setup, run by an agent

**This page is written for a coding agent, not for a human.** If you are a human:
paste the prompt from the README to your own Claude Code / Codex and let it drive.
If you are that agent — this is your checklist. Interview the human, don't assume.

Your goal: after this, your human has their own agent sitting in their Feishu
group chats, and understands how to talk to it.

## 0. Ground rules for you

- **Ask before deciding.** Which repos it may read, which emoji it reacts with,
  how long approvals wait — these are the human's calls, not yours.
- **Never invent credentials.** Auth is done by the human through browser flows;
  you only run the commands and show them the links/QR codes.
- **Verify each step actually worked** before moving on. A green exit code is not
  proof — read the output.

## 1. Check the machine

```bash
which claude          # Claude Code — required
which lark-cli        # Feishu CLI — required
python3 --version     # 3.9+
```

Missing `claude`? Point them to Claude Code's install docs. Missing `lark-cli`?
It ships with the Feishu/Lark CLI toolkit — they install it, not you.

## 2. Give them a bot

If `lark-cli auth status --json --verify` already shows both a ready `bot` and a
ready `user` identity, skip to step 3.

Otherwise run `lark-cli config init --new` **in the background**, read the
verification URL from its output, render it with `lark-cli auth qrcode <url>`,
and hand both to the human. Wait for them to say they're done. Then
`lark-cli auth login --domain im --no-wait --json`, show that URL too, and
finish with `lark-cli auth login --device-code <code>` once they confirm.

Both identities matter: the **bot** speaks and receives mentions; the **user**
(them) reads group history for context.

Last step here: tell them to add their bot to the groups where they want it
summonable (Feishu group settings → bots). A bot can only be @'d where it's a
member.

## 3. Interview them, then write the config

Ask these one at a time — each answer changes the config:

1. **Which directories may it read without asking?** (their main repo, worktrees,
   this bridge's checkout). Everything outside these needs approval per read.
   → `allowed_read_roots`
2. **Where should it run commands from?** Usually a checkout dedicated to the
   agent, not the tree they're editing. → `workdir`
3. **How long should an approval card wait before it gives up?** Default 5
   minutes. → `approvals.timeout_seconds`
4. **Replies in the main chat flow, or inside threads?** → `reply_style`
   (`chat` / `thread`)
5. **Which emoji should it drop when summoned?** They can name one, or set it
   later by reacting and DM-ing `emoji that` — explain that trick, it's the
   reliable way to get an emoji whose API key nobody knows.

Then write `~/.talk-to-my-agent/config.json` from `config.example.json`, filling
in `bot_open_id` and `owner_open_id` from `lark-cli auth status --json`
(`identities.bot.openId` and `identities.user.openId` — don't mix them up).

## 4. Headless auth for Claude

`claude -p` cannot use the keychain login. Have them run `claude setup-token`
(browser flow, one year validity), then store it:

```bash
touch ~/.talk-to-my-agent/env && chmod 600 ~/.talk-to-my-agent/env
# append: CLAUDE_CODE_OAUTH_TOKEN=<their token>
```

If they're behind a proxy, the same file is where `https_proxy` / `http_proxy`
belong — the OAuth exchange fails with `ECONNRESET` without them on some
networks.

Never echo the token back into the chat or a log.

## 5. Prove it works before you automate it

Run `python3 bridge.py` in the foreground. Ask the human to @ their bot in a
group with something real ("what does X do in our codebase?"). Watch for:

1. the ack emoji lands within a second or two,
2. the agent's answer appears in the chat,
3. `~/.talk-to-my-agent/home/<group>/CLAUDE.md` now exists — that's its memory.

Then have them try a write ("create a test file in the repo") so they see the
🔐 approval card and learn the YES / ✔ / NO taps.

Only once that passes, install the launchd service from `launchd/`
(see [setup.md](setup.md) — the `__PATH__` substitution is not optional).

## 6. Hand over

Tell them, in their language, the three things they need to know:

- **@ it in a group** to summon it. Each group gets its own agent with its own
  memory of that room.
- **DM it** to configure: `status`, `model opus`, `emoji that`, `reset <group>`,
  `help`.
- **Approvals are theirs alone**: reads inside their repos are free, everything
  else asks, and only their tap counts.

Then get out of the way — from here on, it's their colleague, not your project.
