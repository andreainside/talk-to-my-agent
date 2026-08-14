# Playbook — what a chat full of agents can do

The bridge is deliberately tiny: @mention → context → local agent → threaded reply. Everything below is a *pattern on top*, not a feature to build into the bridge. Steal freely.

## Mid-conversation summon (the core move)

You're three messages into debating how the cache behaves. Someone realizes this is checkable. `@Bob's agent — settle this.` It reads the debate, greps the actual code, answers with file:line receipts. The debate ends because *evidence showed up*, not because someone got tired.

## Async standup

`@Alice's agent — where did the migration land?` Her agent reads her checkout's git state and answers, while Alice is asleep in another timezone. Nobody prepares status updates; the repo *is* the status update.

## Dual-engine bake-off

`+both is this fix safe to backport?` Two engines, same context, two independent answers, side by side in one thread. Continuous, zero-ceremony model evaluation on your team's *real* questions — better than any benchmark you'd construct.

## Cross-machine relay

Your agent hits a wall: the answer lives in a repo only your teammate has checked out, behind credentials only they hold. You @ their agent with what you know so far; their machine picks up where yours stopped. Two laptops, two contexts, one thread.

## The question that becomes a coding session

A teammate asks your agent something gnarly. It investigates for five minutes and posts findings — plus a session id. You `claude --resume <id>` and you're *inside that investigation*, context loaded, half the work done. Their question was your onboarding.

## Feedback loop closer

Feedback group post → someone @s the owner's agent → it triages against the codebase, links the responsible module, and (once you wire approvals) opens the fix PR. The thread that reported the bug is the thread that announces the fix.

## Alert first-responder

Monitoring bot posts an alert card → on-call @s their agent → it pulls logs/traces read-only and replies with a one-line diagnosis and evidence: noise or real, blast radius, likely cause. The human decision starts from a briefing, not from a blank Grafana tab.

## Meeting researcher

Pair the bridge with a meeting-bot: "can someone check whether that's actually true?" → @agent in the meeting group → answer arrives before the meeting ends. Action items stop being "look into X" and start being resolved in-room.

## Team memory archaeology

Agents with memory systems can answer *why*: `@her agent — why did we reject the queue-based design last quarter?` New teammates interrogate the veterans' agents instead of interrupting the veterans.

---

## Patterns to respect while playing

- **One summon, one thread.** Threads keep parallel investigations from trampling each other — and threads *are* sessions.
- **Agents never approve their own writes.** Anything mutating goes through the owner. The group can ask; only the owner can allow.
- **Loud failure beats silent success.** A timed-out agent says so in the thread. Silence means something is broken — treat it that way.
