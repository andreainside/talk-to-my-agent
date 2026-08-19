# Changelog

Each release gets one section. The bridge reads the newest section and DMs it
to the owner verbatim — so write for the person who'll read it in a chat, not
for a compiler. Mark config changes with ⚠.

## v0.6.2 — 2026-08-19

- **Fix: agents still died at launch on v0.6.1.** Two flags were passed that the
  CLI refuses together (`--append-system-prompt` and its `-file` form), so every
  agent exited in 0.2s while the bridge reported a successful start. Memory and
  the workspace briefing now travel as one prompt.
- **Agent stderr is kept** (`~/.talk-to-my-agent/agent-errors.log`) and a launch
  that dies within seconds is logged as a failure. Discarding stderr is why two
  releases in a row a dead agent looked like a silent one.

## v0.6.1 — 2026-08-19

- **Fix: agents died at startup after v0.6.0.** Moving their working directory
  into your repository also made them inherit the repository's hooks, and
  SessionStart hooks written for interactive sessions hang a headless one. They
  now load only your user-level settings: repo rules and skills still apply,
  repo hooks don't.

## v0.6.0 — 2026-08-19

- **Agents now work inside your repository.** Previously an agent's working
  directory was its own home, so your repo's AGENTS.md/CLAUDE.md rules and
  project skills were invisible to it — it reasoned about your code without
  knowing your conventions. Now cwd is your `workdir`; its own memory still
  loads from its home. Sessions and memory carry over; nobody is re-hired.
- **A topic follows the agent that opened it.** When an agent posts into
  another group (e.g. relaying a request for you), replies on that thread route
  back to *that* agent — not to whichever agent lives in that room. Invisible
  to humans: same bot, same emoji.
- **Agents hand topics to each other silently** when a mention clearly belongs
  to a colleague (inbox handoff, one hop max). Bot lines in context are tagged
  `[bot]` so an agent never mistakes a colleague's words for its own.
- **Release notifications.** The bridge checks for a newer release once a day
  (a `git fetch`, zero tokens) and DMs you the changelog. Reply `update` to
  switch and restart; say nothing to stay. `status` shows your version.
- DM `reload` restarts the bridge in place — no launchctl needed.
- Agents can read your session archives without asking (checking on your other
  sessions is part of the job).

## v0.5.0 — 2026-08-18

- **Codex backend**: set `"backend": "codex"`; same colleague-per-group model,
  same approval policy, real OS sandbox.
- **Zone-based permissions** replace the read-only command allowlist: free
  inside the workspace, ask outside; destructive actions ask when they reach
  out; outward actions (push, PR, publish) always ask.
- **Approval cards in plain language**, answered by tapping YES / ✔ / NO.
  ✔ lasts exactly one task.
- **Handoff to your own dev session**: say 移交 and the agent prepares a warm
  session you resume from CLI or Desktop.
- Agents can read this project's source and their own settings, so they can
  explain and help change their own behaviour; they can file issues here.
- A shared `TEAM.md` all agents on a machine can read and write.
- Workdir is hard-reset to `origin/main` when a task starts, so diagnosis
  always runs against GitHub's latest.

## v0.4.0 — 2026-08-15

- **One persistent agent per group**, each with its own home and self-written
  `CLAUDE.md` memory. Summons stream into the live session; ask mid-task and it
  answers.
- Owner-only DM control plane: `status`, `model`, `emoji that`, `reset`.

## v0.1.0 — 2026-08-14

- First release: @ your bot in a Feishu group, your machine answers.
