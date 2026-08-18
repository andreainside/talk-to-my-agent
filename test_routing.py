"""Replay of 2026-08-18: the CC-bridge agent opened a thread in Ship it! by
posting to it; a human then @'d the bot inside that thread. Old behaviour: the
Ship-it agent (no context) answered. Required: the CC-bridge agent answers.
Second scenario: a foreign-topic mention on the main flow (no thread) — the
Ship-it agent hands it over via inbox; the CC-bridge agent is summoned once,
and a re-handoff is refused."""
import json, os, sys, tempfile, time, threading
from pathlib import Path
os.environ["TTMA_HOME"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bridge

CC, SHIP = "oc_CCBRIDGE", "oc_SHIPIT"
ROOT, HUMAN_MSG, THREAD = "om_root_from_cc", "om_xiaotu_reply", "omt_ship_thread"

# ---- stub lark: the Ship-it thread, rooted by our bot's cross-group post
def fake_lark(*args, **kw):
    a = list(args)
    if "+threads-messages-list" in a:
        return {"ok": True, "data": {"messages": [
            {"message_id": ROOT, "create_time": time.strftime("%Y-%m-%d %H:%M"),
             "sender": {"name": "Andrea M.O.Bot", "sender_type": "app"}, "content": "代张之湄转达…"},
            {"message_id": HUMAN_MSG, "create_time": time.strftime("%Y-%m-%d %H:%M"),
             "sender": {"name": "小涂", "sender_type": "user"}, "content": "@Andrea M.O.Bot 我也在写这个代码，到底谁来写"},
        ]}}
    if "+messages-mget" in a:
        return {"ok": True, "data": {"messages": [{"message_id": HUMAN_MSG, "thread_id": THREAD}]}}
    if "+chat-messages-list" in a:
        return {"ok": True, "data": {"messages": []}}
    if "chats" in a and "get" in a:
        cid = json.loads(a[a.index("--params") + 1])["chat_id"]
        return {"ok": True, "data": {"name": {"oc_CCBRIDGE": "CC 桥实验", "oc_SHIPIT": "Ship it!"}[cid]}}
    return {"ok": True, "data": {}}
bridge.lark = fake_lark
bridge.react = lambda *a, **k: None
bridge.reply = lambda *a, **k: {"ok": True}
bridge.sync_workdir = lambda cfg: None

# ---- capture which agent gets summoned
summoned = []
class FakeAgent:
    backend = "claude"
    def __init__(self, cfg, state, chat_id):
        self.cfg, self.state, self.chat_id = cfg, state, chat_id
        self.busy_since = None; self.last_request = ""; self.session_id = "s-" + chat_id
        self.name = bridge.chat_name(state, chat_id)
        self.home = bridge.ensure_home(state, chat_id)
    def send(self, text):
        summoned.append((self.chat_id, text)); return True
bridge.make_agent = lambda cfg, state, cid: FakeAgent(cfg, state, cid)

cfg = {"bot_open_id": "ou_bot", "owner_open_id": "ou_owner", "workdir": tempfile.mkdtemp(),
       "approvals": {"enabled": False}, "ack_emoji": "SMUG", "reply_style": "chat"}
state = {"chat_names": {CC: "CC 桥实验", SHIP: "Ship it!"}}
agents = {}

# ---- ledger: the CC-bridge agent posted into Ship it! (what the hook records)
ledger = Path(os.environ["TTMA_HOME"]) / "outbound.jsonl"
ledger.write_text(json.dumps({"agent_chat": CC, "target": SHIP, "at": time.time()}) + "\n")

print("=== 场景 1: 小涂在 CC 桥员工开的 Ship it! thread 里 @ ===")
bridge.handle_mention(cfg, state, agents, {
    "message_id": HUMAN_MSG, "chat_id": SHIP, "sender_id": "ou_xiaotu", "sender_type": "user",
    "content": "@Andrea M.O.Bot 我也在写这个代码，到底谁来写",
    "mentions": [{"id": "ou_bot", "name": "Andrea M.O.Bot"}], "thread_id": THREAD,
})
who = summoned[-1][0] if summoned else None
print("  路由到:", who, "| 期望:", CC)
assert who == CC, "FAIL: 仍然路由给了 Ship-it 员工"
assert "another group" in summoned[-1][1] and "Ship it!" in summoned[-1][1], "FAIL: 没告诉它这是在别的群"
print("  PASS 话题跟着开口的人走(Ship-it 员工全程未被召唤)")

print("\n=== 场景 2: 主流消息,无 thread → Ship-it 员工接到后判定是同事的,写 inbox ===")
summoned.clear()
bridge.owning_agent_chat = lambda *a, **k: None   # no ledger claim on main flow
bridge.thread_of = lambda mid: None
bridge.handle_mention(cfg, state, agents, {
    "message_id": "om_mainflow", "chat_id": SHIP, "sender_id": "ou_xiaotu", "sender_type": "user",
    "content": "@Andrea M.O.Bot 那个 deepseek 的事怎么样了",
    "mentions": [{"id": "ou_bot", "name": "Andrea M.O.Bot"}],
})
assert summoned[-1][0] == SHIP, "主流消息应先到本群员工"
print("  Ship-it 员工收到 ✓ (它会按手册判断:上下文里的 [bot] 不是我说的 → 写同事 inbox)")

# the Ship-it agent writes the handoff note (what the handbook tells it to do)
cc_inbox = bridge.HOMES_DIR / bridge.safe_dir_name("CC 桥实验") / "inbox"
cc_inbox.mkdir(parents=True, exist_ok=True)
(cc_inbox / "h1.json").write_text(json.dumps({
    "message_id": "om_mainflow", "chat_id": SHIP, "thread_id": None, "sender_id": "ou_xiaotu",
    "content": "那个 deepseek 的事怎么样了", "from_chat": SHIP,
    "note": "上下文里的 [bot] 转达是 CC 桥同事发的,DeepSeek 这条线是它在跟", "hops": 0}))
summoned.clear()
t = threading.Thread(target=bridge.watch_inboxes, args=(cfg, state, agents), daemon=True); t.start()
time.sleep(5)
assert summoned and summoned[-1][0] == CC, f"FAIL: inbox 转交没到 CC 桥员工, got {summoned}"
assert "handed to you by your colleague" in summoned[-1][1] and "Ship it!" in summoned[-1][1]
assert not list(cc_inbox.glob("*.json")), "inbox note should be consumed"
print("  PASS inbox 转交 → CC 桥员工被召唤,带同事的判断理由,人类零感知")

print("\n=== 场景 3: 已经转过一次的不再转(防乒乓) ===")
summoned.clear()
(cc_inbox / "h2.json").write_text(json.dumps({
    "message_id": "om_x", "chat_id": SHIP, "sender_id": "ou_x", "content": "y",
    "from_chat": SHIP, "note": "again", "hops": 1}))
time.sleep(5)
assert not summoned, "FAIL: hops=1 的转交单不该再触发召唤"
assert not list(cc_inbox.glob("*.json")), "note should still be consumed"
print("  PASS hops≥1 丢弃")

print("\n=== 场景 4: [bot] 标记进上下文 ===")
lines = bridge.format_lines([  # newest first, like the API returns
    {"message_id": "b", "create_time": "t2", "sender": {"name": "小涂", "sender_type": "user"}, "content": "收到"},
    {"message_id": "a", "create_time": "t1", "sender": {"name": "Andrea M.O.Bot", "sender_type": "app"}, "content": "转达一下"},
])
assert "Andrea M.O.Bot [bot]:" in lines[0] and "[bot]" not in lines[1]
print("  PASS bot 发言带 [bot] 标记,人类不带")
print("\nALL PASS")
