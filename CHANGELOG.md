# Changelog

Each release gets one section. The bridge reads the newest section and DMs it
to the owner verbatim — so write for the person who'll read it in a chat, not
for a compiler. Mark config changes with ⚠.

## v0.7.1 — 2026-08-19

- **A release gate that actually launches an agent** (`./release.sh`), which
  caught a wrong claim on its first run: a repo's own CLAUDE.md/AGENTS.md is
  *reachable* to an agent, not auto-injected — it reads those files when the
  work calls for it. Docs corrected. Two
  releases shipped broken because the checks proved a one-off command could see
  the repo, never that a real agent survived its launch flags. Now a release
  can't be cut unless an agent starts, answers, and proves both its repo rules
  and its own memory arrived.
- Feishu's "bot is invisible to user ids" refusal is translated: it names the
  person and points at the availability-scope switch in the developer console.
- README tells people running pre-v0.6.0 copies how to upgrade once, by hand.

## v0.7.0 — 2026-08-19

- **Agents can reach people now.** Blocked on a permission, a collision with
  someone else's work, or a decision only a person can make? Instead of guessing
  or stalling, an agent asks that person in chat.
- **1:1 rooms**: `pair <name>` in your DM opens a room with you, them, and both
  your agents. One address per person means no agent ever has to guess which
  team room a topic belongs to. Posting there is free; opening a conversation in
  a team room asks you first — that's your voice in public.
- **The directory grows by asking.** `shared/TEAM.md` starts empty. When an
  agent doesn't know who owns something it asks you, and once the contact works
  it writes the line itself. No org chart to fill in.
- **`ask-the-team` skill** gives your own dev sessions the same reflex.

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
