# Setup (per person, ~20 minutes)

Every teammate runs their **own** bridge with their **own** bot. Nothing is shared.

## 1. Feishu side

1. Install [`lark-cli`](https://open.feishu.cn) and run `lark-cli config init` — this creates your personal bot app. Complete the auth flow (`lark-cli auth login`) so both identities work:
   - **bot** identity: sends replies, receives @mention events, drops reactions
   - **user** identity: reads group history as you (bots usually can't read history; you can)
2. Note the two ids you'll need for config: `lark-cli auth status --json` shows your **user open_id** and your **bot open_id**.
3. Add your bot to the groups where you want to be summonable (group settings → bots, or ask any member to add it).

Scopes worth checking if something 403s: `im:message` (bot send), `im:message.reactions:write_only` (bot react), `im:message:readonly` + `im:chat:read` (user read). The error envelopes name the missing scope explicitly.

## 2. Machine side

```bash
git clone https://github.com/andreainside/talk-to-my-agent.git
cd talk-to-my-agent
mkdir -p ~/.talk-to-my-agent
cp config.example.json ~/.talk-to-my-agent/config.json
$EDITOR ~/.talk-to-my-agent/config.json     # fill in the ids and workdir
```

**Workdir**: give the agent a dedicated checkout of your repo (not the one you're editing in), and keep it fresh — a `git fetch && git reset --hard origin/main` cron, or just let the agent be told it may be slightly behind. Never point it at a dirty working tree you care about.

## 3. Run it

Foreground first, to see it breathe:

```bash
python3 bridge.py
```

Have someone @ your bot in a group. You should see: instant emoji → (up to a few minutes) → answer in thread.

Then keep it alive with launchd (macOS):

```bash
sed -e "s|__PROJECT_DIR__|$(pwd)|" -e "s|__HOME__|$HOME|" launchd/com.talk-to-my-agent.plist.example \
  > ~/Library/LaunchAgents/com.talk-to-my-agent.plist
launchctl load ~/Library/LaunchAgents/com.talk-to-my-agent.plist
```

Logs land in `~/.talk-to-my-agent/bridge.log`.

## 4. Choose your engine

The bridge shells out to whatever agent CLIs you have on PATH:

- **Claude Code** — `claude -p`, headless with a read-only tool allowlist; sessions are resumable (`claude --resume <id>` turns any summoned run into your interactive session).
- **Codex** — `codex exec --sandbox read-only`.

DM your bot `model claude` / `model codex` to pick your default; see [configuration.md](configuration.md) for models, effort, and your signature emoji.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| No emoji, no answer | bridge not running, or bot not actually in that group |
| Emoji but no answer | executor failed/timed out — check `bridge.log`; the bridge also posts the error into the thread |
| `access denied` reading history | user identity missing read scopes, or you're not a member of that group |
| Bot can't be @'d | bots must be group members to be mentionable |
